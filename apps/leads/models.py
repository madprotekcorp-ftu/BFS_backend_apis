from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils import timezone

from common.choices import CLOSED_STATUSES, OPEN_STATUSES, LeadSource, LeadStatus
from common.models import TimeStampedModel


def lead_code_for(pk):
    return f"BFS-{pk:06d}"


class LeadQuerySet(models.QuerySet):
    def active(self):
        """Leads that are not soft-deleted. Use this for every list, search, export and count."""
        return self.filter(is_deleted=False)

    def open(self):
        return self.filter(status__in=OPEN_STATUSES)

    def followup_due(self, today=None):
        """The one follow-up rule: next_followup_date <= today (IST) and not converted/closed."""
        today = today or timezone.localdate()
        return self.filter(next_followup_date__lte=today).exclude(status__in=CLOSED_STATUSES)


class Lead(TimeStampedModel):
    # Null until the row is inserted, then BFS- + zero-padded primary key.
    lead_code = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    customer_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=10, db_index=True)
    location = models.CharField(max_length=120, blank=True, default="")
    service = models.ForeignKey("catalog.ServiceCategory", on_delete=models.PROTECT, related_name="leads")
    loan_amount = models.CharField(max_length=50, blank=True, default="")
    occupation = models.CharField(max_length=120, blank=True, default="")
    message = models.TextField(blank=True, default="", validators=[MaxLengthValidator(2000)])
    consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=LeadSource.choices)
    status = models.CharField(max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True)
    assigned_employee = models.ForeignKey(
        "employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    last_followup_date = models.DateField(null=True, blank=True)
    next_followup_date = models.DateField(null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    import_batch = models.ForeignKey(
        "imports.ImportBatch", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["created_at"], name="lead_created_at_idx")]

    def __str__(self):
        return self.lead_code or f"Lead #{self.pk}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.lead_code:
            self.lead_code = lead_code_for(self.pk)
            type(self).objects.filter(pk=self.pk).update(lead_code=self.lead_code)


class LeadRemark(TimeStampedModel):
    """Append-only internal note on a lead."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="remarks")
    text = models.TextField(validators=[MaxLengthValidator(2000)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Remark on {self.lead_id}"
