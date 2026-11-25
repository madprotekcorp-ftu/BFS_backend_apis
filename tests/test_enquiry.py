import pytest

from apps.catalog.models import ServiceCategory
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

URL = "/api/public/enquiries/"


def payload(service, **overrides):
    data = {
        "customer_name": "Ravi Kumar",
        "mobile": "9876543210",
        "location": "Hosur",
        "service_id": service.pk,
        "loan_amount": "25 lakh",
        "occupation": "Salaried",
        "message": "Need home loan",
        "consent": True,
        "website": "",
    }
    data.update(overrides)
    return data


def test_enquiry_creates_website_lead_with_status_new(api_client, service):
    response = api_client.post(URL, payload(service, source="phone", status="converted"), format="json")
    assert response.status_code == 201
    body = response.json()
    lead = Lead.objects.get()
    assert body == {
        "success": True,
        "data": {"reference": lead.lead_code},
        "message": "Thank you. Our team will contact you shortly.",
    }
    assert lead.lead_code == f"BFS-{lead.pk:06d}"
    assert lead.source == "website"
    assert lead.status == "new"
    assert lead.consent is True and lead.consent_at is not None
    assert lead.created_by is None


@pytest.mark.parametrize("raw", ["+91 98765 43210", "919876543210", "09876543210", "98765-43210"])
def test_mobile_prefixes_are_normalised(api_client, service, raw):
    response = api_client.post(URL, payload(service, mobile=raw), format="json")
    assert response.status_code == 201
    assert Lead.objects.get().mobile == "9876543210"


@pytest.mark.parametrize("raw", ["5876543210", "98765", "98765432101", "abcdefghij", ""])
def test_bad_mobile_is_rejected(api_client, service, raw):
    response = api_client.post(URL, payload(service, mobile=raw), format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "mobile" in error["fields"]


def test_missing_or_false_consent_is_rejected(api_client, service):
    data = payload(service)
    del data["consent"]
    assert "consent" in api_client.post(URL, data, format="json").json()["error"]["fields"]
    response = api_client.post(URL, payload(service, consent=False), format="json")
    assert response.status_code == 400
    assert "consent" in response.json()["error"]["fields"]


def test_inactive_service_is_rejected(api_client, service):
    ServiceCategory.objects.filter(pk=service.pk).update(is_active=False)
    response = api_client.post(URL, payload(service), format="json")
    assert response.status_code == 400
    assert "service_id" in response.json()["error"]["fields"]


def test_honeypot_submission_is_not_saved(api_client, service):
    response = api_client.post(URL, payload(service, website="http://spam.example"), format="json")
    assert response.status_code == 201
    assert Lead.objects.count() == 0


def test_enquiry_is_throttled_to_five_per_hour(api_client, service):
    for i in range(5):
        assert api_client.post(URL, payload(service, mobile=f"987654321{i}"), format="json").status_code == 201
    response = api_client.post(URL, payload(service), format="json")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


def test_duplicate_website_enquiry_is_accepted_and_flagged(api_client, admin_client, service):
    api_client.post(URL, payload(service), format="json")
    api_client.post(URL, payload(service), format="json")
    assert Lead.objects.count() == 2
    lead = Lead.objects.order_by("id").last()
    detail = admin_client.get(f"/api/admin/leads/{lead.pk}/").json()["data"]
    assert detail["possible_duplicate"] is True


def test_message_over_2000_chars_is_rejected(api_client, service):
    response = api_client.post(URL, payload(service, message="x" * 2001), format="json")
    assert "message" in response.json()["error"]["fields"]
