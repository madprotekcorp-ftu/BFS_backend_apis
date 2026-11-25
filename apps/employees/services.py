from django.db import transaction
from django.utils import timezone

from common.exceptions import Conflict

from .models import LeadAssignment


@transaction.atomic
def assign_lead(*, lead, employee, user, note=""):
    """Assign, transfer or (employee=None) unassign a lead, writing a history row.

    The caller should have locked the lead with select_for_update().
    """
    if employee is not None and not employee.is_active:
        raise Conflict("This employee is inactive and cannot receive new leads.")
    if employee is None and lead.assigned_employee_id is None:
        raise Conflict("This lead is not assigned to anyone.")
    if employee is not None and lead.assigned_employee_id == employee.pk:
        raise Conflict("This lead is already assigned to this employee.")

    now = timezone.now()
    LeadAssignment.objects.create(
        lead=lead,
        previous_employee_id=lead.assigned_employee_id,
        new_employee=employee,
        assigned_by=user,
        assigned_at=now,
        note=note or "",
    )
    lead.assigned_employee = employee
    lead.assigned_at = now if employee is not None else None
    lead.save(update_fields=["assigned_employee", "assigned_at", "updated_at"])
    return lead
