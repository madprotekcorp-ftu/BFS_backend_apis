from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.leads.serializers import LeadDetailSerializer
from apps.leads.views import get_active_lead, lead_detail_data
from common.choices import OPEN_STATUSES, LeadStatus
from common.responses import success

from .models import Employee
from .serializers import AssignSerializer, EmployeeSerializer, LeadAssignmentSerializer
from .services import assign_lead


def employee_queryset():
    live = Q(leads__is_deleted=False)
    return Employee.objects.annotate(
        lead_total=Count("leads", filter=live),
        lead_open=Count("leads", filter=live & Q(leads__status__in=OPEN_STATUSES)),
        lead_converted=Count("leads", filter=live & Q(leads__status=LeadStatus.CONVERTED)),
    )


@extend_schema(
    parameters=[
        OpenApiParameter("is_active", bool, description="true or false"),
        OpenApiParameter("search", description="Name, Employee ID, mobile or email"),
    ]
)
class EmployeeListCreateView(generics.ListCreateAPIView):
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        queryset = employee_queryset().order_by("name", "id")
        params = self.request.query_params
        is_active = (params.get("is_active") or "").lower()
        if is_active in ("true", "1"):
            queryset = queryset.filter(is_active=True)
        elif is_active in ("false", "0"):
            queryset = queryset.filter(is_active=False)
        elif is_active:
            raise ValidationError({"is_active": ["Use true or false."]})
        term = (params.get("search") or "").strip()
        if term:
            queryset = queryset.filter(
                Q(name__icontains=term)
                | Q(employee_code__icontains=term)
                | Q(mobile__icontains=term)
                | Q(email__icontains=term)
            )
        return queryset

    def post(self, request, *args, **kwargs):
        serializer = EmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        data = EmployeeSerializer(employee_queryset().get(pk=employee.pk)).data
        return success(data, "Employee created", status.HTTP_201_CREATED)


class EmployeeDetailView(generics.RetrieveUpdateAPIView):
    """No delete: deactivate instead (is_active=false) so history stays intact."""

    serializer_class = EmployeeSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return employee_queryset()

    def patch(self, request, *args, **kwargs):
        employee = get_object_or_404(Employee, pk=kwargs["pk"])
        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = EmployeeSerializer(employee_queryset().get(pk=employee.pk)).data
        return success(data, "Employee updated")


class LeadAssignView(APIView):
    """Assign, transfer, or (employee_id=null) unassign a lead."""

    @extend_schema(request=AssignSerializer, responses=LeadDetailSerializer)
    def post(self, request, pk):
        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee_id = serializer.validated_data["employee_id"]
        note = serializer.validated_data.get("note", "")

        with transaction.atomic():
            lead = get_active_lead(pk, for_update=True)
            employee = None
            if employee_id is not None:
                employee = Employee.objects.filter(pk=employee_id).first()
                if employee is None:
                    raise ValidationError({"employee_id": ["Employee not found."]})
            assign_lead(lead=lead, employee=employee, user=request.user, note=note)

        message = "Lead assigned" if employee is not None else "Lead unassigned"
        return success(lead_detail_data(pk), message)


class LeadAssignmentListView(generics.ListAPIView):
    """Assignment history for a lead, newest first."""

    serializer_class = LeadAssignmentSerializer

    def get_queryset(self):
        lead = get_active_lead(self.kwargs["pk"])
        return lead.assignments.select_related("previous_employee", "new_employee", "assigned_by").order_by(
            "-assigned_at", "-id"
        )
