from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import ServiceCategory
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

URL = "/api/admin/leads/"


def create_payload(service, **overrides):
    data = {
        "customer_name": "Anita Rao",
        "mobile": "9988776655",
        "service_id": service.pk,
        "source": "phone",
    }
    data.update(overrides)
    return data


def test_manual_create_returns_detail_and_sets_created_by(admin_client, admin_user, service, make_employee):
    employee = make_employee()
    next_date = (timezone.localdate() + timedelta(days=2)).isoformat()
    response = admin_client.post(
        URL,
        create_payload(service, status="contacted", assigned_employee_id=employee.pk, next_followup_date=next_date),
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Lead created"
    data = body["data"]
    assert data["lead_code"].startswith("BFS-")
    assert data["source"] == {"code": "phone", "label": "Phone Call"}
    assert data["status"] == {"code": "contacted", "label": "Contacted"}
    assert data["assigned_employee"] == {"id": employee.pk, "name": employee.name}
    assert data["created_by"] == {"id": admin_user.pk, "name": "BFS Admin"}
    assert data["next_followup_date"] == next_date
    assert data["created_at"].endswith("+05:30")
    for key in ("document_count", "remark_count", "possible_duplicate", "import_batch_id", "consent_at"):
        assert key in data
    lead = Lead.objects.get(pk=data["id"])
    assert lead.assignments.count() == 1


def test_manual_create_rejects_website_source(admin_client, service):
    response = admin_client.post(URL, create_payload(service, source="website"), format="json")
    assert response.status_code == 400
    assert "source" in response.json()["error"]["fields"]


def test_manual_create_duplicate_mobile_conflict(admin_client, service, make_lead):
    existing = make_lead(mobile="9988776655")
    response = admin_client.post(URL, create_payload(service, mobile="+91 99887 76655"), format="json")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "duplicate_mobile"
    assert error["existing_lead_id"] == existing.pk

    response = admin_client.post(URL, create_payload(service, allow_duplicate=True), format="json")
    assert response.status_code == 201
    assert response.json()["data"]["possible_duplicate"] is True


def test_manual_create_with_inactive_employee_conflicts(admin_client, service, make_employee):
    employee = make_employee(is_active=False)
    response = admin_client.post(URL, create_payload(service, assigned_employee_id=employee.pk), format="json")
    assert response.status_code == 409
    assert Lead.objects.count() == 0


def test_edit_fields_status_and_followups(admin_client, make_lead, service):
    lead = make_lead()
    other_service = ServiceCategory.objects.get(slug="gold-loan")
    response = admin_client.patch(
        f"{URL}{lead.pk}/",
        {
            "customer_name": "Renamed",
            "mobile": "+91 9123456780",
            "service_id": other_service.pk,
            "status": "converted",
            "next_followup_date": "2026-12-01",
            "last_followup_date": "2026-11-20",
        },
        format="json",
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["customer_name"] == "Renamed"
    assert data["mobile"] == "9123456780"
    assert data["service"] == {"id": other_service.pk, "name": "Gold Loan"}
    assert data["status"]["code"] == "converted"
    assert data["next_followup_date"] == "2026-12-01"
    assert data["last_followup_date"] == "2026-11-20"


def test_source_cannot_change_to_or_from_website(admin_client, make_lead):
    lead = make_lead(source="phone")
    response = admin_client.patch(f"{URL}{lead.pk}/", {"source": "website"}, format="json")
    assert response.status_code == 400
    web = make_lead(source="website")
    response = admin_client.patch(f"{URL}{web.pk}/", {"source": "phone"}, format="json")
    assert response.status_code == 400
    assert admin_client.patch(f"{URL}{lead.pk}/", {"source": "referral"}, format="json").status_code == 200


def test_patch_cannot_change_assignment(admin_client, make_lead, make_employee):
    lead = make_lead()
    response = admin_client.patch(f"{URL}{lead.pk}/", {"assigned_employee_id": make_employee().pk}, format="json")
    assert response.status_code == 400
    assert "assigned_employee_id" in response.json()["error"]["fields"]


def test_soft_delete_hides_lead_everywhere(admin_client, make_lead):
    lead = make_lead()
    assert admin_client.delete(f"{URL}{lead.pk}/").status_code == 204
    lead.refresh_from_db()
    assert lead.is_deleted is True
    assert admin_client.get(f"{URL}{lead.pk}/").status_code == 404
    assert admin_client.get(URL).json()["pagination"]["total"] == 0
    assert admin_client.get("/api/admin/dashboard/").json()["data"]["summary"]["total_leads"] == 0


def test_unknown_lead_is_404(admin_client):
    response = admin_client.get(f"{URL}99999/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_row_shape_and_pagination(admin_client, make_lead):
    for _ in range(25):
        make_lead()
    body = admin_client.get(URL, {"page_size": 10, "page": 2}).json()
    assert body["pagination"] == {"page": 2, "page_size": 10, "total": 25, "total_pages": 3}
    assert len(body["data"]) == 10
    assert set(body["data"][0]) == {
        "id", "lead_code", "customer_name", "mobile", "service", "location", "source", "status",
        "assigned_employee", "created_at", "next_followup_date",
    }
    assert admin_client.get(URL, {"page_size": 500}).json()["pagination"]["page_size"] == 100


def test_search_by_name_mobile_and_code(admin_client, make_lead):
    ravi = make_lead(customer_name="Ravi Kumar", mobile="9876543210")
    make_lead(customer_name="Someone Else", mobile="9123456789")

    def ids(**params):
        return [row["id"] for row in admin_client.get(URL, params).json()["data"]]

    assert ids(search="ravi") == [ravi.pk]
    assert ids(search="54321") == [ravi.pk]
    assert ids(search=ravi.lead_code) == [ravi.pk]


def test_filters(admin_client, make_lead, make_employee):
    employee = make_employee()
    today = timezone.localdate()
    a = make_lead(status="new", source="phone", assigned_employee=employee, next_followup_date=today)
    b = make_lead(status="contacted", source="walk_in", next_followup_date=today - timedelta(days=1))
    c = make_lead(status="converted", source="referral", next_followup_date=today - timedelta(days=3))
    d = make_lead(status="interested", source="phone", next_followup_date=today + timedelta(days=1))
    gold = ServiceCategory.objects.get(slug="gold-loan")
    e = make_lead(status="closed", source="other", service=gold)
    Lead.objects.filter(pk=e.pk).update(created_at=timezone.now() - timedelta(days=10))

    def ids(**params):
        response = admin_client.get(URL, params)
        assert response.status_code == 200, response.json()
        return sorted(row["id"] for row in response.json()["data"])

    assert ids(status="new,contacted") == sorted([a.pk, b.pk])
    assert ids(source="phone") == sorted([a.pk, d.pk])
    assert ids(service_id=str(gold.pk)) == [e.pk]
    assert ids(employee_id=str(employee.pk)) == [a.pk]
    assert ids(employee_id="unassigned") == sorted([b.pk, c.pk, d.pk, e.pk])
    assert ids(followup_due="true") == sorted([a.pk, b.pk])  # converted lead c excluded
    ten_days_ago = (today - timedelta(days=10)).isoformat()
    assert ids(date_from=ten_days_ago, date_to=ten_days_ago) == [e.pk]
    assert ids(date_from=today.isoformat()) == sorted([a.pk, b.pk, c.pk, d.pk])

    assert admin_client.get(URL, {"status": "bogus"}).status_code == 400
    assert admin_client.get(URL, {"date_from": "24-11-2026"}).status_code == 400


def test_ordering(admin_client, make_lead):
    make_lead(customer_name="Zara")
    make_lead(customer_name="Aarav")
    names = [r["customer_name"] for r in admin_client.get(URL, {"ordering": "customer_name"}).json()["data"]]
    assert names == ["Aarav", "Zara"]
    names = [r["customer_name"] for r in admin_client.get(URL, {"ordering": "-customer_name"}).json()["data"]]
    assert names == ["Zara", "Aarav"]
    assert admin_client.get(URL, {"ordering": "mobile"}).status_code == 400


def test_remarks_add_and_list_newest_first(admin_client, admin_user, make_lead):
    lead = make_lead()
    url = f"{URL}{lead.pk}/remarks/"
    first = admin_client.post(url, {"text": "Called, asked for salary slips"}, format="json")
    assert first.status_code == 201
    data = first.json()["data"]
    assert set(data) == {"id", "text", "created_by", "created_at"}
    assert data["created_by"] == {"id": admin_user.pk, "name": "BFS Admin"}
    admin_client.post(url, {"text": "Second call"}, format="json")

    listing = admin_client.get(url).json()
    assert [r["text"] for r in listing["data"]] == ["Second call", "Called, asked for salary slips"]
    assert admin_client.get(f"{URL}{lead.pk}/").json()["data"]["remark_count"] == 2
    assert admin_client.post(url, {"text": ""}, format="json").status_code == 400
    assert admin_client.post(url, {"text": "x" * 2001}, format="json").status_code == 400
