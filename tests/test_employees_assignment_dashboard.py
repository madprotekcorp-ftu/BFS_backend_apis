from datetime import timedelta

import pytest
from django.utils import timezone

from apps.leads.models import Lead

pytestmark = pytest.mark.django_db


# --- Employees ----------------------------------------------------------------------


def test_create_and_update_employee(admin_client):
    response = admin_client.post(
        "/api/admin/employees/",
        {"employee_code": "EMP100", "name": "Priya", "mobile": "+91 98400 12345", "email": "priya@example.com"},
        format="json",
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["mobile"] == "9840012345"
    assert data["is_active"] is True
    assert data["lead_counts"] == {"total": 0, "open": 0, "converted": 0}

    response = admin_client.patch(f"/api/admin/employees/{data['id']}/", {"is_active": False}, format="json")
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False
    assert admin_client.get(f"/api/admin/employees/{data['id']}/").json()["data"]["employee_code"] == "EMP100"


def test_employee_code_must_be_unique(admin_client, make_employee):
    make_employee(employee_code="EMP200")
    response = admin_client.post("/api/admin/employees/", {"employee_code": "emp200", "name": "X"}, format="json")
    assert response.status_code == 400
    assert "employee_code" in response.json()["error"]["fields"]


def test_employees_cannot_be_deleted(admin_client, make_employee):
    employee = make_employee()
    assert admin_client.delete(f"/api/admin/employees/{employee.pk}/").status_code == 405


def test_employee_list_lead_counts_and_filters(admin_client, make_employee, make_lead):
    priya = make_employee(name="Priya")
    old = make_employee(name="Old Staff", is_active=False)
    make_lead(assigned_employee=priya, status="new")
    make_lead(assigned_employee=priya, status="follow_up")
    make_lead(assigned_employee=priya, status="converted")
    make_lead(assigned_employee=priya, status="closed")
    make_lead(assigned_employee=priya, status="new", is_deleted=True)  # ignored

    rows = {r["id"]: r for r in admin_client.get("/api/admin/employees/").json()["data"]}
    assert rows[priya.pk]["lead_counts"] == {"total": 4, "open": 2, "converted": 1}

    active = admin_client.get("/api/admin/employees/", {"is_active": "true"}).json()["data"]
    assert [r["id"] for r in active] == [priya.pk]
    inactive = admin_client.get("/api/admin/employees/", {"is_active": "false"}).json()["data"]
    assert [r["id"] for r in inactive] == [old.pk]
    found = admin_client.get("/api/admin/employees/", {"search": "pri"}).json()["data"]
    assert [r["id"] for r in found] == [priya.pk]


# --- Assignment ---------------------------------------------------------------------


def test_assign_transfer_unassign_and_history(admin_client, admin_user, make_lead, make_employee):
    lead = make_lead()
    priya, arjun = make_employee(name="Priya"), make_employee(name="Arjun")
    url = f"/api/admin/leads/{lead.pk}/assign/"

    response = admin_client.post(url, {"employee_id": priya.pk}, format="json")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["assigned_employee"] == {"id": priya.pk, "name": "Priya"}
    assert data["assigned_at"] is not None

    response = admin_client.post(url, {"employee_id": arjun.pk, "note": "Priya on leave"}, format="json")
    assert response.json()["data"]["assigned_employee"]["id"] == arjun.pk

    response = admin_client.post(url, {"employee_id": None}, format="json")
    assert response.status_code == 200
    assert response.json()["data"]["assigned_employee"] is None

    history = admin_client.get(f"/api/admin/leads/{lead.pk}/assignments/").json()["data"]
    assert len(history) == 3
    assert history[1]["previous_employee"] == {"id": priya.pk, "name": "Priya"}
    assert history[1]["new_employee"] == {"id": arjun.pk, "name": "Arjun"}
    assert history[1]["note"] == "Priya on leave"
    assert history[1]["assigned_by"] == {"id": admin_user.pk, "name": "BFS Admin"}
    assert history[0]["new_employee"] is None
    assert history[2]["previous_employee"] is None


def test_assign_conflicts(admin_client, make_lead, make_employee):
    lead = make_lead()
    inactive = make_employee(is_active=False)
    active = make_employee()
    url = f"/api/admin/leads/{lead.pk}/assign/"

    response = admin_client.post(url, {"employee_id": inactive.pk}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"

    assert admin_client.post(url, {"employee_id": None}, format="json").status_code == 409
    assert admin_client.post(url, {"employee_id": active.pk}, format="json").status_code == 200
    assert admin_client.post(url, {"employee_id": active.pk}, format="json").status_code == 409
    assert admin_client.post(url, {"employee_id": 99999}, format="json").status_code == 400
    assert lead.assignments.count() == 1


def test_deactivating_employee_keeps_their_leads(admin_client, make_lead, make_employee):
    employee = make_employee()
    lead = make_lead(assigned_employee=employee)
    admin_client.patch(f"/api/admin/employees/{employee.pk}/", {"is_active": False}, format="json")
    lead.refresh_from_db()
    assert lead.assigned_employee_id == employee.pk
    counts = admin_client.get("/api/admin/dashboard/").json()["data"]["employee_counts"]
    assert any(row["employee_id"] == employee.pk and row["total"] == 1 for row in counts)


# --- Dashboard ----------------------------------------------------------------------


def test_dashboard_counts_match_database(admin_client, make_lead, make_employee):
    today = timezone.localdate()
    priya = make_employee(name="Priya")
    make_lead(status="new", source="website", next_followup_date=today, assigned_employee=priya)
    make_lead(status="new", source="phone", next_followup_date=today - timedelta(days=2))
    make_lead(status="converted", source="phone", next_followup_date=today - timedelta(days=1),
              assigned_employee=priya)
    make_lead(status="closed", source="walk_in", next_followup_date=today)
    make_lead(status="follow_up", source="referral", next_followup_date=today + timedelta(days=5))
    make_lead(status="interested", source="referral", next_followup_date=today + timedelta(days=30))
    make_lead(status="new", source="phone", is_deleted=True, next_followup_date=today)

    data = admin_client.get("/api/admin/dashboard/").json()["data"]
    assert data["summary"] == {"total_leads": 6, "new_leads": 2, "followups_due": 2, "converted_leads": 1}
    assert data["summary"]["followups_due"] == Lead.objects.active().followup_due().count()
    status_counts = {row["code"]: row["count"] for row in data["status_distribution"]}
    assert status_counts == {"new": 2, "contacted": 0, "interested": 1, "follow_up": 1, "converted": 1, "closed": 1}
    source_counts = {row["code"]: row["count"] for row in data["source_distribution"]}
    assert source_counts["phone"] == 2 and source_counts["website"] == 1
    assert data["unassigned_count"] == 4
    priya_row = next(r for r in data["employee_counts"] if r["employee_id"] == priya.pk)
    assert (priya_row["total"], priya_row["open"], priya_row["converted"]) == (2, 1, 1)
    assert len(data["recent_leads"]) == 6
    # Overdue + next 7 days, open leads only, sorted by date.
    upcoming = [row["next_followup_date"] for row in data["upcoming_followups"]]
    assert upcoming == sorted(upcoming) and len(upcoming) == 3


def test_dashboard_filters(admin_client, make_lead):
    make_lead(status="new", source="phone")
    make_lead(status="new", source="website")
    data = admin_client.get("/api/admin/dashboard/", {"source": "phone"}).json()["data"]
    assert data["summary"]["total_leads"] == 1
