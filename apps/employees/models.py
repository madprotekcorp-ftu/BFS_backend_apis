from django.conf import settings
from django.db import models
from django.utils import timezone

from common.models import TimeStampedModel


class Employee(TimeStampedModel):
    """Directory record only. Employees never get a login."""

    employee_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=10, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Inactive staff cannot receive new leads.")

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name} ({self.employee_code})"


class LeadAssignment(TimeStampedModel):
    """One row per assign / transfer / unassign of a lead. new_employee is null for an unassign."""

    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="assignments")
    previous_employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    new_employee = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-assigned_at", "-id"]
