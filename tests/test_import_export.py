import csv
import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.imports.models import ImportBatch
from apps.leads.models import Lead

pytestmark = pytest.mark.django_db

IMPORT_URL = "/api/admin/leads/import/"


def read_csv(response):
    content = b"".join(response.streaming_content).decode("utf-8")
    assert content.startswith("﻿")
    return list(csv.reader(io.StringIO(content.lstrip("﻿"))))


def csv_file(text, name="old-leads.csv"):
    return SimpleUploadedFile(name, text.encode("utf-8"), content_type="text/csv")


# --- Export ---------------------------------------------------------------------------


def test_export_honours_filters_and_escapes_formulas(admin_client, make_lead):
    make_lead(customer_name="=HYPERLINK(\"http://evil\")", status="new", message="@SUM(A1)")
    make_lead(customer_name="Closed Person", status="closed")
    response = admin_client.get("/api/admin/leads/export/", {"status": "new"})
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert 'filename="bfs-leads-' in response["Content-Disposition"]
    rows = read_csv(response)
    assert rows[0][:3] == ["Lead ID", "Customer Name", "Mobile"]
    assert len(rows) == 2
    assert rows[1][1] == "'=HYPERLINK(\"http://evil\")"
    assert rows[1][-1] == "'@SUM(A1)"


def test_export_excludes_deleted(admin_client, make_lead):
    make_lead(is_deleted=True)
    rows = read_csv(admin_client.get("/api/admin/leads/export/"))
    assert len(rows) == 1


# --- Import ---------------------------------------------------------------------------


def test_csv_import_preview_confirm_and_report(admin_client, admin_user, make_lead):
    make_lead(mobile="9000000099")
    text = (
        " Customer Name ,MOBILE,service,location,next_followup_date\n"
        "Ravi,9876543210,Home Loan,Hosur,2026-12-01\n"       # row 2 valid (name)
        "Meena,+91 91234 56780,gold-loan,,\n"                # row 3 valid (slug)
        ",9123456781,home-loan,,\n"                           # row 4 invalid: name missing
        "Bad Mobile,12345,home-loan,,\n"                     # row 5 invalid: mobile
        "Bad Service,9123456782,Spaceship Loan,,\n"          # row 6 invalid: service
        "Bad Date,9123456783,home-loan,,31-31-2026\n"        # row 7 invalid: date
        "Existing,9000000099,home-loan,,\n"                  # row 8 duplicate: in DB
        "Repeat,9876543210,home-loan,,\n"                    # row 9 duplicate: in file
        ",,,,\n"                                              # blank row skipped
    )
    response = admin_client.post(IMPORT_URL, {"file": csv_file(text)}, format="multipart")
    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    assert data["status"] == "preview"
    assert data["filename"] == "old-leads.csv"
    assert data["summary"]["total_rows"] == 8
    assert data["summary"]["valid_rows"] == 2
    assert data["summary"]["invalid_rows"] == 4
    assert data["summary"]["duplicate_rows"] == 2
    assert "successful_rows" not in data["summary"]  # only after confirm
    assert data["rows_pagination"] == {"page": 1, "page_size": 20, "total": 8, "total_pages": 1}
    assert "pagination" not in response.json()
    assert Lead.objects.count() == 1  # nothing imported yet
    results = {row["row_number"]: row["result"] for row in data["rows"]}
    assert results == {2: "valid", 3: "valid", 4: "invalid", 5: "invalid", 6: "invalid", 7: "invalid",
                       8: "duplicate", 9: "duplicate"}

    batch_id = data["batch_id"]
    invalid = admin_client.get(f"{IMPORT_URL}{batch_id}/", {"result": "invalid"}).json()
    assert invalid["data"]["rows_pagination"]["total"] == 4
    assert invalid["data"]["rows"][0]["errors"] == [{"field": "customer_name", "message": "This value is required."}]

    response = admin_client.post(f"{IMPORT_URL}{batch_id}/confirm/")
    assert response.status_code == 200
    summary = response.json()["data"]
    assert (summary["total_rows"], summary["successful_rows"], summary["failed_rows"], summary["duplicate_rows"]) == (
        8, 2, 4, 2,
    )
    imported = Lead.objects.filter(import_batch_id=batch_id).order_by("id")
    assert [lead.mobile for lead in imported] == ["9876543210", "9123456780"]
    lead = imported[0]
    assert (lead.source, lead.status, lead.created_by_id) == ("existing_db", "new", admin_user.pk)
    assert lead.lead_code == f"BFS-{lead.pk:06d}"
    assert str(lead.next_followup_date) == "2026-12-01"
    assert lead.service.slug == "home-loan"

    completed = admin_client.get(f"{IMPORT_URL}{batch_id}/").json()["data"]
    assert completed["status"] == "completed"
    assert completed["summary"]["successful_rows"] == 2 and completed["summary"]["failed_rows"] == 4

    assert admin_client.post(f"{IMPORT_URL}{batch_id}/confirm/").status_code == 409
    assert admin_client.post(f"{IMPORT_URL}{batch_id}/cancel/").status_code == 409

    report = read_csv(admin_client.get(f"{IMPORT_URL}{batch_id}/report/"))
    assert report[0][-3:] == ["row_number", "result", "errors"]
    assert len(report) == 1 + 6


def test_missing_required_columns_returns_400_without_batch(admin_client):
    response = admin_client.post(IMPORT_URL, {"file": csv_file("name,phone\nRavi,9876543210\n")}, format="multipart")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "missing_columns"
    assert error["missing_columns"] == ["customer_name", "mobile", "service"]
    assert ImportBatch.objects.count() == 0


def test_xlsx_import(admin_client):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["customer_name", "mobile", "service", "next_followup_date"])
    sheet.append(["Excel Person", 9876543210, "Personal Loan", None])
    buffer = io.BytesIO()
    workbook.save(buffer)
    upload = SimpleUploadedFile("leads.xlsx", buffer.getvalue())
    response = admin_client.post(IMPORT_URL, {"file": upload}, format="multipart")
    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    assert data["summary"]["valid_rows"] == 1
    admin_client.post(f"{IMPORT_URL}{data['batch_id']}/confirm/")
    assert Lead.objects.get().mobile == "9876543210"


def test_confirm_rechecks_duplicates_created_after_preview(admin_client, make_lead):
    response = admin_client.post(
        IMPORT_URL, {"file": csv_file("customer_name,mobile,service\nRavi,9876543210,home-loan\n")}, format="multipart"
    )
    batch_id = response.json()["data"]["batch_id"]
    make_lead(mobile="9876543210")
    summary = admin_client.post(f"{IMPORT_URL}{batch_id}/confirm/").json()["data"]
    assert summary["successful_rows"] == 0 and summary["duplicate_rows"] == 1


def test_cancel_preview(admin_client):
    response = admin_client.post(
        IMPORT_URL, {"file": csv_file("customer_name,mobile,service\nRavi,9876543210,home-loan\n")}, format="multipart"
    )
    batch_id = response.json()["data"]["batch_id"]
    assert admin_client.post(f"{IMPORT_URL}{batch_id}/cancel/").json()["data"]["status"] == "cancelled"
    assert admin_client.post(f"{IMPORT_URL}{batch_id}/confirm/").status_code == 409
    assert Lead.objects.count() == 0


def test_import_rejects_wrong_type_and_too_many_rows(admin_client, settings):
    upload = SimpleUploadedFile("leads.txt", b"hello")
    assert admin_client.post(IMPORT_URL, {"file": upload}, format="multipart").status_code == 415
    settings.IMPORT_MAX_ROWS = 2
    text = "customer_name,mobile,service\n" + "".join(f"P{i},987654321{i},home-loan\n" for i in range(3))
    response = admin_client.post(IMPORT_URL, {"file": csv_file(text)}, format="multipart")
    assert response.status_code == 400
    assert "file" in response.json()["error"]["fields"]


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_template_download(admin_client, fmt):
    response = admin_client.get("/api/admin/leads/import/template/", {"format": fmt})
    assert response.status_code == 200
    assert f"bfs-lead-import-template.{fmt}" in response["Content-Disposition"]
    if fmt == "csv":
        rows = read_csv(response)
        assert rows[0] == ["customer_name", "mobile", "service", "location", "loan_amount", "occupation", "message",
                           "next_followup_date"]
        assert len(rows) == 3
    else:
        sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
        assert sheet.max_row == 3


def test_template_samples_import_cleanly(admin_client):
    template = b"".join(admin_client.get("/api/admin/leads/import/template/").streaming_content)
    upload = SimpleUploadedFile("template.csv", template)
    data = admin_client.post(IMPORT_URL, {"file": upload}, format="multipart").json()["data"]
    assert data["summary"]["valid_rows"] == 2


def test_cleanup_command_cancels_old_previews(admin_client):
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    response = admin_client.post(
        IMPORT_URL, {"file": csv_file("customer_name,mobile,service\nRavi,9876543210,home-loan\n")}, format="multipart"
    )
    batch_id = response.json()["data"]["batch_id"]
    ImportBatch.objects.filter(pk=batch_id).update(created_at=timezone.now() - timedelta(hours=25))
    call_command("cleanup_import_previews")
    assert ImportBatch.objects.get(pk=batch_id).status == "cancelled"
