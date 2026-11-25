"""Lead list filters, shared by the list, the CSV export and the dashboard."""

import re

from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.choices import LeadSource, LeadStatus
from common.dates import parse_date_param, start_of_day, start_of_next_day

ALL_FILTERS = (
    "search",
    "status",
    "source",
    "service_id",
    "employee_id",
    "date_from",
    "date_to",
    "followup_due",
)
DASHBOARD_FILTERS = ("date_from", "date_to", "status", "source", "employee_id")
ORDERING_FIELDS = ("created_at", "next_followup_date", "customer_name", "status")
DEFAULT_ORDERING = "-created_at"


def _csv(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _int_list(value, field, errors):
    try:
        return [int(v) for v in _csv(value)]
    except ValueError:
        errors[field] = ["Use whole-number IDs, separated by commas."]
        return []


def apply_lead_filters(queryset, params, fields=ALL_FILTERS):
    errors = {}

    if "search" in fields:
        term = (params.get("search") or "").strip()
        if term:
            condition = Q(customer_name__icontains=term) | Q(lead_code__icontains=term)
            digits = re.sub(r"[\s\-]", "", term)
            if digits:
                condition |= Q(mobile__icontains=digits)
            queryset = queryset.filter(condition)

    for field, choices in (("status", LeadStatus), ("source", LeadSource)):
        if field in fields:
            values = _csv(params.get(field))
            if values:
                unknown = [v for v in values if v not in choices.values]
                if unknown:
                    errors[field] = [f"Unknown value(s): {', '.join(unknown)}."]
                else:
                    queryset = queryset.filter(**{f"{field}__in": values})

    if "service_id" in fields:
        ids = _int_list(params.get("service_id"), "service_id", errors)
        if ids:
            queryset = queryset.filter(service_id__in=ids)

    if "employee_id" in fields:
        value = (params.get("employee_id") or "").strip()
        if value == "unassigned":
            queryset = queryset.filter(assigned_employee__isnull=True)
        elif value:
            ids = _int_list(value, "employee_id", errors)
            if ids:
                queryset = queryset.filter(assigned_employee_id__in=ids)

    # created_at date range, inclusive, in IST.
    if "date_from" in fields and params.get("date_from"):
        try:
            day = parse_date_param(params["date_from"], "date_from")
            queryset = queryset.filter(created_at__gte=start_of_day(day))
        except ValidationError as exc:
            errors.update(exc.detail)
    if "date_to" in fields and params.get("date_to"):
        try:
            day = parse_date_param(params["date_to"], "date_to")
            queryset = queryset.filter(created_at__lt=start_of_next_day(day))
        except ValidationError as exc:
            errors.update(exc.detail)

    if "followup_due" in fields:
        value = (params.get("followup_due") or "").strip().lower()
        if value in ("true", "1"):
            queryset = queryset.followup_due(timezone.localdate())
        elif value not in ("", "false", "0"):
            errors["followup_due"] = ["Use true or false."]

    if errors:
        raise ValidationError(errors)
    return queryset


def apply_lead_ordering(queryset, ordering):
    ordering = (ordering or DEFAULT_ORDERING).strip()
    if ordering.lstrip("-") not in ORDERING_FIELDS:
        raise ValidationError(
            {"ordering": [f"Order by one of: {', '.join(ORDERING_FIELDS)} (prefix - for descending)."]}
        )
    tie_breaker = "-id" if ordering.startswith("-") else "id"
    if ordering.lstrip("-") == "next_followup_date":
        field = F("next_followup_date")
        expression = field.desc(nulls_last=True) if ordering.startswith("-") else field.asc(nulls_last=True)
        return queryset.order_by(expression, tie_breaker)
    return queryset.order_by(ordering, tie_breaker)
