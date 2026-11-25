"""Import policy (also published in the API docs):

1. Required columns: customer_name, mobile, service. Header matching is case-insensitive and trims spaces.
2. A row is invalid if a required value is missing, the mobile fails validation, the service is
   unknown, or a date cannot be parsed.
3. A row is a duplicate if its mobile already exists in the database or appeared earlier in the
   same file (in an earlier valid row).
4. On confirm only valid rows are imported; invalid and duplicate rows are skipped, never partly
   imported and never overwrite existing leads.
5. Imported leads get source=existing_db, status=new, created_by = admin, import_batch = the batch.
6. Previews older than 24 hours are cancelled by `manage.py cleanup_import_previews`.
"""

from datetime import datetime

from django.utils import timezone

from apps.catalog.models import ServiceCategory
from apps.leads.models import Lead
from common.choices import ImportRowResult
from common.validators import MOBILE_ERROR, normalize_mobile

TEMPLATE_COLUMNS = [
    "customer_name",
    "mobile",
    "service",
    "location",
    "loan_amount",
    "occupation",
    "message",
    "next_followup_date",
]
REQUIRED_COLUMNS = ["customer_name", "mobile", "service"]
MAX_LENGTHS = {"customer_name": 150, "location": 120, "loan_amount": 50, "occupation": 120, "message": 2000}
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"]


def parse_flexible_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError


class ServiceLookup:
    """Matches a service by name or slug, case-insensitively."""

    def __init__(self):
        self._by_key = {}
        for service in ServiceCategory.objects.all():
            self._by_key[service.name.strip().lower()] = service.pk
            self._by_key[service.slug.strip().lower()] = service.pk

    def find(self, text):
        return self._by_key.get(text.strip().lower())


def validate_row(data, services):
    """Return (cleaned, errors). cleaned holds Lead field values when errors is empty."""
    errors = []
    cleaned = {}

    for field in REQUIRED_COLUMNS:
        if not data.get(field, "").strip():
            errors.append({"field": field, "message": "This value is required."})

    name = data.get("customer_name", "").strip()
    if name:
        cleaned["customer_name"] = name

    mobile = data.get("mobile", "").strip()
    if mobile:
        try:
            cleaned["mobile"] = normalize_mobile(mobile)
        except ValueError:
            errors.append({"field": "mobile", "message": MOBILE_ERROR})

    service_text = data.get("service", "").strip()
    if service_text:
        service_id = services.find(service_text)
        if service_id is None:
            errors.append({"field": "service", "message": f'Unknown service "{service_text}".'})
        else:
            cleaned["service_id"] = service_id

    for field in ("location", "loan_amount", "occupation", "message"):
        cleaned[field] = data.get(field, "").strip()

    for field, limit in MAX_LENGTHS.items():
        value = data.get(field, "").strip()
        if len(value) > limit:
            errors.append({"field": field, "message": f"Must be at most {limit} characters."})

    followup = data.get("next_followup_date", "").strip()
    cleaned["next_followup_date"] = None
    if followup:
        try:
            cleaned["next_followup_date"] = parse_flexible_date(followup)
        except ValueError:
            errors.append(
                {"field": "next_followup_date", "message": "Could not read this date. Use YYYY-MM-DD."}
            )

    return cleaned, errors


def existing_mobiles(mobiles):
    """{mobile: lead_code} for active leads with any of these mobiles."""
    found = {}
    for mobile, code in (
        Lead.objects.active().filter(mobile__in=set(mobiles)).order_by("id").values_list("mobile", "lead_code")
    ):
        found.setdefault(mobile, code)
    return found


def classify_rows(rows, services):
    """rows: [(row_number, data)] -> [(row_number, data, result, errors, cleaned)]."""
    first_pass = [(number, data, *validate_row(data, services)) for number, data in rows]
    in_database = existing_mobiles(c["mobile"] for _, _, c, e in first_pass if not e)

    seen = {}
    results = []
    for number, data, cleaned, errors in first_pass:
        if errors:
            results.append((number, data, ImportRowResult.INVALID, errors, None))
            continue
        mobile = cleaned["mobile"]
        if mobile in in_database:
            message = f"Mobile number already exists ({in_database[mobile]})."
            results.append((number, data, ImportRowResult.DUPLICATE, [{"field": "mobile", "message": message}], None))
        elif mobile in seen:
            message = f"Same mobile number as row {seen[mobile]} in this file."
            results.append((number, data, ImportRowResult.DUPLICATE, [{"field": "mobile", "message": message}], None))
        else:
            seen[mobile] = number
            results.append((number, data, ImportRowResult.VALID, [], cleaned))
    return results


def sample_rows():
    """Two example rows for the template, using real service names/slugs."""
    loan = ServiceCategory.objects.filter(group="loan", is_active=True).first()
    insurance = ServiceCategory.objects.filter(group="insurance", is_active=True).first() or loan
    today = timezone.localdate().isoformat()
    return [
        ["Ravi Kumar", "9876543210", loan.name if loan else "Home Loan", "Hosur", "25 lakh", "Salaried",
         "Needs a home loan", today],
        ["Meena S", "+91 91234 56780", insurance.slug if insurance else "health-insurance", "Krishnagiri", "",
         "Business", "Family health cover", ""],
    ]
