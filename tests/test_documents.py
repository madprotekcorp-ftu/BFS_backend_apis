import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.documents.models import LeadDocument

pytestmark = pytest.mark.django_db

PDF_BYTES = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def upload(admin_client, lead, name="pan card.pdf", content=PDF_BYTES, category="kyc"):
    return admin_client.post(
        f"/api/admin/leads/{lead.pk}/documents/",
        {"file": SimpleUploadedFile(name, content), "category": category},
        format="multipart",
    )


def test_upload_list_and_download(admin_client, admin_user, make_lead):
    lead = make_lead()
    response = upload(admin_client, lead)
    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    assert set(data) == {"id", "original_filename", "category", "file_size", "mime_type", "uploaded_by", "uploaded_at"}
    assert data["original_filename"] == "pan card.pdf"
    assert data["category"] == {"code": "kyc", "label": "Identity / KYC"}
    assert data["mime_type"] == "application/pdf"
    assert data["file_size"] == len(PDF_BYTES)

    document = LeadDocument.objects.get(pk=data["id"])
    assert document.storage_key.startswith(f"leads/{lead.pk}/")
    assert "pan card" not in document.storage_key
    assert (settings.PRIVATE_MEDIA_ROOT / document.storage_key).exists()

    listing = admin_client.get(f"/api/admin/leads/{lead.pk}/documents/").json()
    assert [d["id"] for d in listing["data"]] == [data["id"]]
    assert admin_client.get(f"/api/admin/leads/{lead.pk}/").json()["data"]["document_count"] == 1

    download = admin_client.get(f"/api/admin/documents/{data['id']}/download/")
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == PDF_BYTES
    assert download["Content-Disposition"].startswith("attachment")
    assert download["X-Content-Type-Options"] == "nosniff"
    assert download["Cache-Control"] == "private, no-store"
    inline = admin_client.get(f"/api/admin/documents/{data['id']}/download/", {"inline": "1"})
    assert inline["Content-Disposition"].startswith("inline")

    assert upload(admin_client, lead, name="photo.png", content=PNG_BYTES, category="other").status_code == 201


def test_download_requires_auth(admin_client, make_lead):
    document_id = upload(admin_client, make_lead()).json()["data"]["id"]
    response = APIClient().get(f"/api/admin/documents/{document_id}/download/")
    assert response.status_code == 401


def test_wrong_type_and_oversize_rejected(admin_client, make_lead, settings):
    lead = make_lead()
    response = upload(admin_client, lead, name="script.exe", content=b"MZ\x90\x00")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"
    # Right extension, wrong content.
    response = upload(admin_client, lead, name="fake.pdf", content=b"<html><script>alert(1)</script></html>")
    assert response.status_code == 415
    response = upload(admin_client, lead, name="fake.png", content=PDF_BYTES)
    assert response.status_code == 415

    settings.DOCUMENT_MAX_SIZE_MB = 0.00005  # ~52 bytes
    response = upload(admin_client, lead)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"

    assert upload(admin_client, lead, category="passport").status_code == 400
    assert LeadDocument.objects.count() == 0


def test_bin_restore_and_purge(admin_client, make_lead, django_capture_on_commit_callbacks):
    lead = make_lead()
    document_id = upload(admin_client, lead).json()["data"]["id"]
    document = LeadDocument.objects.get(pk=document_id)
    path = settings.PRIVATE_MEDIA_ROOT / document.storage_key

    assert admin_client.delete(f"/api/admin/documents/{document_id}/purge/").status_code == 409
    assert admin_client.post(f"/api/admin/documents/{document_id}/restore/").status_code == 409

    assert admin_client.delete(f"/api/admin/documents/{document_id}/").status_code == 204
    assert admin_client.get(f"/api/admin/leads/{lead.pk}/documents/").json()["data"] == []
    assert admin_client.get(f"/api/admin/documents/{document_id}/download/").status_code == 404
    assert path.exists()  # file stays while in the bin
    assert admin_client.delete(f"/api/admin/documents/{document_id}/").status_code == 409

    binned = admin_client.get("/api/admin/documents/bin/").json()
    assert binned["pagination"]["total"] == 1
    row = binned["data"][0]
    assert row["lead"]["lead_code"] == lead.lead_code
    assert row["deleted_by"]["name"] == "BFS Admin"
    assert row["deleted_at"]

    assert admin_client.post(f"/api/admin/documents/{document_id}/restore/").status_code == 200
    assert len(admin_client.get(f"/api/admin/leads/{lead.pk}/documents/").json()["data"]) == 1

    admin_client.delete(f"/api/admin/documents/{document_id}/")
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(f"/api/admin/documents/{document_id}/purge/").status_code == 204
    assert not LeadDocument.objects.filter(pk=document_id).exists()
    assert not path.exists()


def test_documents_hidden_with_deleted_lead(admin_client, make_lead):
    lead = make_lead()
    document_id = upload(admin_client, lead).json()["data"]["id"]
    admin_client.delete(f"/api/admin/leads/{lead.pk}/")
    assert LeadDocument.objects.filter(pk=document_id).exists()  # kept
    assert admin_client.get(f"/api/admin/documents/{document_id}/download/").status_code == 404
    assert admin_client.get(f"/api/admin/leads/{lead.pk}/documents/").status_code == 404
