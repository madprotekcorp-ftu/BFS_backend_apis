import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.employees.models import Employee
from apps.employees.services import assign_lead
from common.choices import OPEN_STATUSES, LeadSource, LeadStatus
from common.csv_utils import csv_download
from common.exceptions import Conflict
from common.responses import no_content, success
from common.throttling import EnquiryThrottle

from .filters import DASHBOARD_FILTERS, apply_lead_filters, apply_lead_ordering
from .models import Lead
from .serializers import (
    AdminLeadCreateSerializer,
    EnquirySerializer,
    LeadDetailSerializer,
    LeadListSerializer,
    LeadUpdateSerializer,
    RemarkSerializer,
)

logger = logging.getLogger(__name__)

ENQUIRY_THANKS = "Thank you. Our team will contact you shortly."

LIST_PARAMS = [
    OpenApiParameter("search", description="Name (contains), mobile (contains) or lead code"),
    OpenApiParameter("status", description="Comma-separated status codes"),
    OpenApiParameter("source", description="Comma-separated source codes"),
    OpenApiParameter("service_id", description="Comma-separated service ids"),
    OpenApiParameter("employee_id", description="Employee id, or 'unassigned'"),
    OpenApiParameter("date_from", description="created_at from (YYYY-MM-DD, IST, inclusive)"),
    OpenApiParameter("date_to", description="created_at to (YYYY-MM-DD, IST, inclusive)"),
    OpenApiParameter("followup_due", description="true = next_followup_date <= today and not converted/closed"),
    OpenApiParameter("ordering", description="created_at, next_followup_date, customer_name, status; prefix - for desc"),
]


def active_leads():
    return Lead.objects.active().select_related("service", "assigned_employee")


def lead_detail_queryset():
    same_mobile = Lead.objects.active().filter(mobile=OuterRef("mobile")).exclude(pk=OuterRef("pk"))
    return (
        active_leads()
        .select_related("created_by")
        .annotate(
            document_count=Count("documents", filter=Q(documents__deleted_at__isnull=True), distinct=True),
            remark_count=Count("remarks", distinct=True),
            possible_duplicate=Exists(same_mobile),
        )
    )


def lead_detail_data(pk):
    return LeadDetailSerializer(get_object_or_404(lead_detail_queryset(), pk=pk)).data


def get_active_lead(pk, *, for_update=False):
    queryset = Lead.objects.active()
    if for_update:
        queryset = queryset.select_for_update()
    return get_object_or_404(queryset, pk=pk)


# --- Public -------------------------------------------------------------------


class EnquiryCreateView(APIView):
    """Website enquiry form. Throttled to 5 per IP per hour."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [EnquiryThrottle]

    @extend_schema(
        request=EnquirySerializer,
        responses={201: inline_serializer("EnquiryResponse", {"reference": serializers.CharField()})},
    )
    def post(self, request):
        if str(request.data.get("website") or "").strip():
            # Honeypot filled in: almost certainly a bot. Pretend it worked, save nothing.
            logger.info("Enquiry honeypot triggered; submission dropped")
            fake_reference = f"BFS-{secrets.randbelow(900000) + 100000:06d}"
            return success({"reference": fake_reference}, ENQUIRY_THANKS, status.HTTP_201_CREATED)

        serializer = EnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("website", None)
        lead = Lead.objects.create(
            **data,
            source=LeadSource.WEBSITE,
            status=LeadStatus.NEW,
            consent_at=timezone.now(),
        )
        logger.info("Website enquiry received: %s", lead.lead_code)
        return success({"reference": lead.lead_code}, ENQUIRY_THANKS, status.HTTP_201_CREATED)


# --- Admin: leads ---------------------------------------------------------------


@extend_schema(parameters=LIST_PARAMS)
class LeadListCreateView(generics.ListCreateAPIView):
    serializer_class = LeadListSerializer

    def get_queryset(self):
        params = self.request.query_params
        return apply_lead_ordering(apply_lead_filters(active_leads(), params), params.get("ordering"))

    @extend_schema(request=AdminLeadCreateSerializer, responses={201: LeadDetailSerializer})
    def post(self, request, *args, **kwargs):
        serializer = AdminLeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        allow_duplicate = data.pop("allow_duplicate")
        employee_id = data.pop("assigned_employee_id", None)

        if not allow_duplicate:
            existing = Lead.objects.active().filter(mobile=data["mobile"]).order_by("id").first()
            if existing is not None:
                raise Conflict(
                    "A lead with this mobile number already exists.",
                    code="duplicate_mobile",
                    extra={"existing_lead_id": existing.pk, "existing_lead_code": existing.lead_code},
                )

        with transaction.atomic():
            lead = Lead(**data, created_by=request.user)
            if lead.consent:
                lead.consent_at = timezone.now()
            lead.save()
            if employee_id is not None:
                employee = Employee.objects.get(pk=employee_id)
                assign_lead(lead=lead, employee=employee, user=request.user)

        return success(lead_detail_data(lead.pk), "Lead created", status.HTTP_201_CREATED)


class LeadDetailView(APIView):
    @extend_schema(responses=LeadDetailSerializer)
    def get(self, request, pk):
        return success(lead_detail_data(pk))

    @extend_schema(request=LeadUpdateSerializer, responses=LeadDetailSerializer)
    def patch(self, request, pk):
        lead = get_active_lead(pk)
        serializer = LeadUpdateSerializer(instance=lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(lead, field, value)
        lead.save()
        return success(lead_detail_data(pk), "Lead updated")

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        lead = get_active_lead(pk)
        lead.is_deleted = True
        lead.save(update_fields=["is_deleted", "updated_at"])
        logger.info("Lead %s soft-deleted by user %s", lead.lead_code, request.user.pk)
        return no_content()


EXPORT_HEADER = [
    "Lead ID",
    "Customer Name",
    "Mobile",
    "Service",
    "Location",
    "Source",
    "Status",
    "Assigned Employee",
    "Created At",
    "Next Follow-up Date",
    "Occupation",
    "Loan Amount",
    "Message",
]


class LeadExportView(APIView):
    """CSV of the filtered lead list (same filters as the list, no pagination)."""

    @extend_schema(parameters=LIST_PARAMS, responses={(200, "text/csv"): bytes})
    def get(self, request):
        params = request.query_params
        queryset = apply_lead_ordering(apply_lead_filters(active_leads(), params), params.get("ordering"))

        def rows():
            for lead in queryset.iterator(chunk_size=500):
                yield [
                    lead.lead_code,
                    lead.customer_name,
                    lead.mobile,
                    lead.service.name,
                    lead.location,
                    lead.get_source_display(),
                    lead.get_status_display(),
                    lead.assigned_employee.name if lead.assigned_employee else "",
                    timezone.localtime(lead.created_at).strftime("%Y-%m-%d %H:%M"),
                    lead.next_followup_date.isoformat() if lead.next_followup_date else "",
                    lead.occupation,
                    lead.loan_amount,
                    lead.message,
                ]

        filename = f"bfs-leads-{timezone.localtime():%Y%m%d-%H%M}.csv"
        return csv_download(filename, EXPORT_HEADER, rows())


# --- Admin: remarks -----------------------------------------------------------------


class LeadRemarkListCreateView(generics.ListCreateAPIView):
    """Append-only internal notes, newest first."""

    serializer_class = RemarkSerializer

    def get_lead(self):
        if not hasattr(self, "_lead"):
            self._lead = get_active_lead(self.kwargs["pk"])
        return self._lead

    def get_queryset(self):
        return self.get_lead().remarks.select_related("created_by").order_by("-created_at", "-id")

    def post(self, request, *args, **kwargs):
        lead = self.get_lead()
        serializer = RemarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        remark = serializer.save(lead=lead, created_by=request.user)
        return success(RemarkSerializer(remark).data, "Remark added", status.HTTP_201_CREATED)


# --- Admin: dashboard ---------------------------------------------------------------


class DashboardView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("date_from", description="created_at from (YYYY-MM-DD, IST)"),
            OpenApiParameter("date_to", description="created_at to (YYYY-MM-DD, IST)"),
            OpenApiParameter("status"),
            OpenApiParameter("source"),
            OpenApiParameter("employee_id", description="Employee id, or 'unassigned'"),
        ],
        responses=inline_serializer("Dashboard", {"summary": serializers.DictField()}),
    )
    def get(self, request):
        params = request.query_params
        leads = apply_lead_filters(Lead.objects.active(), params, fields=DASHBOARD_FILTERS).order_by()
        today = timezone.localdate()
        due = Q(next_followup_date__lte=today, status__in=OPEN_STATUSES)

        totals = leads.aggregate(
            total=Count("id"),
            new=Count("id", filter=Q(status=LeadStatus.NEW)),
            due=Count("id", filter=due),
            converted=Count("id", filter=Q(status=LeadStatus.CONVERTED)),
            unassigned=Count("id", filter=Q(assigned_employee__isnull=True)),
        )

        by_status = dict(leads.values_list("status").annotate(n=Count("id")))
        by_source = dict(leads.values_list("source").annotate(n=Count("id")))

        per_employee = {
            row["assigned_employee"]: row
            for row in leads.filter(assigned_employee__isnull=False)
            .values("assigned_employee")
            .annotate(
                total=Count("id"),
                open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
                converted=Count("id", filter=Q(status=LeadStatus.CONVERTED)),
            )
        }
        # Active staff always appear; inactive staff appear while they still hold leads,
        # so the admin can see and transfer them.
        employees = Employee.objects.filter(Q(is_active=True) | Q(pk__in=per_employee.keys()))
        employee_filter = (params.get("employee_id") or "").strip()
        if employee_filter == "unassigned":
            employees = employees.none()
        elif employee_filter:
            employees = employees.filter(pk__in=[int(v) for v in employee_filter.split(",") if v.strip()])

        employee_counts = []
        for employee in employees.order_by("name", "id"):
            row = per_employee.get(employee.pk, {})
            employee_counts.append(
                {
                    "employee_id": employee.pk,
                    "name": employee.name,
                    "is_active": employee.is_active,
                    "total": row.get("total", 0),
                    "open": row.get("open", 0),
                    "converted": row.get("converted", 0),
                }
            )

        listed = leads.select_related("service", "assigned_employee")
        recent = listed.order_by("-created_at", "-id")[:10]
        upcoming = listed.filter(
            next_followup_date__lte=today + timedelta(days=7), status__in=OPEN_STATUSES
        ).order_by("next_followup_date", "id")[:20]

        data = {
            "summary": {
                "total_leads": totals["total"],
                "new_leads": totals["new"],
                "followups_due": totals["due"],
                "converted_leads": totals["converted"],
            },
            "status_distribution": [
                {"code": code, "label": label, "count": by_status.get(code, 0)} for code, label in LeadStatus.choices
            ],
            "source_distribution": [
                {"code": code, "label": label, "count": by_source.get(code, 0)} for code, label in LeadSource.choices
            ],
            "employee_counts": employee_counts,
            "unassigned_count": totals["unassigned"],
            "recent_leads": LeadListSerializer(recent, many=True).data,
            "upcoming_followups": LeadListSerializer(upcoming, many=True).data,
        }
        return success(data)
