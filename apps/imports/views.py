import io
from pathlib import Path

import openpyxl
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView

from apps.leads.models import Lead, lead_code_for
from common.choices import ImportBatchStatus, ImportRowResult, LeadSource, LeadStatus
from common.csv_utils import csv_download
from common.exceptions import ApiError, Conflict, FileTooLarge, UnsupportedFileType
from common.pagination import StandardPagination
from common.responses import success

from .models import ImportBatch, ImportRow
from .parsing import ImportFileError, read_rows
from .validation import (
    REQUIRED_COLUMNS,
    TEMPLATE_COLUMNS,
    ServiceLookup,
    classify_rows,
    existing_mobiles,
    sample_rows,
    validate_row,
)

ALLOWED_EXTENSIONS = (".csv", ".xlsx")
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ImportUpload = inline_serializer("ImportUpload", {"file": serializers.FileField()})


class ImportRowSerializer(serializers.ModelSerializer):
    lead_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = ImportRow
        fields = ["row_number", "result", "data", "errors", "lead_id"]


def batch_summary(batch):
    counts = batch.rows.aggregate(
        total=Count("id"),
        valid=Count("id", filter=Q(result=ImportRowResult.VALID)),
        invalid=Count("id", filter=Q(result=ImportRowResult.INVALID)),
        duplicate=Count("id", filter=Q(result=ImportRowResult.DUPLICATE)),
        imported=Count("id", filter=Q(result=ImportRowResult.IMPORTED)),
    )
    return {
        "total_rows": counts["total"],
        "valid_rows": counts["valid"],
        "invalid_rows": counts["invalid"],
        "duplicate_rows": counts["duplicate"],
        "successful_rows": counts["imported"],
        "failed_rows": counts["invalid"],
    }


def batch_response(batch, request, view, response_status=status.HTTP_200_OK, message=None):
    """Batch details plus one page of rows (filter with ?result=invalid,duplicate&page=N)."""
    rows = batch.rows.order_by("row_number")
    result_filter = [r.strip() for r in (request.query_params.get("result") or "").split(",") if r.strip()]
    if result_filter:
        unknown = [r for r in result_filter if r not in ImportRowResult.values]
        if unknown:
            raise ValidationError({"result": [f"Unknown value(s): {', '.join(unknown)}."]})
        rows = rows.filter(result__in=result_filter)

    paginator = StandardPagination()
    page = paginator.paginate_queryset(rows, request, view=view)
    data = {
        "batch_id": str(batch.pk),
        "status": batch.status,
        "filename": batch.filename,
        "created_at": serializers.DateTimeField().to_representation(batch.created_at),
        "imported_at": serializers.DateTimeField().to_representation(batch.imported_at)
        if batch.imported_at
        else None,
        "summary": batch_summary(batch),
        "missing_columns": [],
        "rows": ImportRowSerializer(page, many=True).data,
    }
    return success(data, message, response_status, pagination=paginator.pagination_meta())


class ImportUploadView(APIView):
    """Upload a .csv/.xlsx (max 5 MB). Parses and validates only; nothing is imported yet.

    See the import policy in the API description.
    """

    parser_classes = [MultiPartParser]

    @extend_schema(request={"multipart/form-data": ImportUpload}, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": ["Please choose a .csv or .xlsx file to upload."]})
        extension = Path(upload.name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileType("Only .csv and .xlsx files can be imported.")
        if upload.size > settings.IMPORT_MAX_FILE_SIZE_MB * 1024 * 1024:
            raise FileTooLarge(f"Import files must be {settings.IMPORT_MAX_FILE_SIZE_MB} MB or smaller.")

        try:
            headers, rows = read_rows(upload, extension, settings.IMPORT_MAX_ROWS)
        except ImportFileError as exc:
            raise ValidationError({"file": [str(exc)]})

        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            message = f"The file is missing required column(s): {', '.join(missing)}."
            raise ApiError(
                message,
                code="validation_error",
                status_code=status.HTTP_400_BAD_REQUEST,
                extra={"fields": {"file": [message]}, "missing_columns": missing},
            )
        if not rows:
            raise ValidationError({"file": ["The file has a header row but no data rows."]})

        classified = classify_rows(rows, ServiceLookup())
        with transaction.atomic():
            batch = ImportBatch.objects.create(
                filename=Path(upload.name).name[:255],
                imported_by=request.user,
                total_rows=len(classified),
            )
            ImportRow.objects.bulk_create(
                ImportRow(batch=batch, row_number=number, data=data, result=result, errors=errors)
                for number, data, result, errors, _ in classified
            )
        return batch_response(batch, request, self, status.HTTP_201_CREATED, "File checked. Review and confirm.")


@extend_schema(
    parameters=[OpenApiParameter("result", description="valid, invalid, duplicate, imported")],
    responses=OpenApiTypes.OBJECT,
)
class ImportBatchDetailView(APIView):
    def get(self, request, batch_id):
        batch = get_object_or_404(ImportBatch, pk=batch_id)
        return batch_response(batch, request, self)


class ImportConfirmView(APIView):
    """Imports the valid rows in one transaction. 409 if the batch is not in preview."""

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, batch_id):
        with transaction.atomic():
            batch = get_object_or_404(ImportBatch.objects.select_for_update(), pk=batch_id)
            if batch.status != ImportBatchStatus.PREVIEW:
                raise Conflict(f"This import is already {batch.status}.")

            # Re-check valid rows: a lead with the same mobile may have been added since the preview.
            services = ServiceLookup()
            rows = list(batch.rows.filter(result=ImportRowResult.VALID).order_by("row_number"))
            checked = [(row, *validate_row(row.data, services)) for row in rows]
            in_database = existing_mobiles(c["mobile"] for _, c, e in checked if not e)

            to_import = []
            for row, cleaned, errors in checked:
                if errors:
                    row.result, row.errors = ImportRowResult.INVALID, errors
                elif cleaned["mobile"] in in_database:
                    row.result = ImportRowResult.DUPLICATE
                    row.errors = [
                        {"field": "mobile", "message": f"Mobile number already exists ({in_database[cleaned['mobile']]})."}
                    ]
                else:
                    to_import.append((row, cleaned))

            leads = Lead.objects.bulk_create(
                Lead(
                    **cleaned,
                    source=LeadSource.EXISTING_DB,
                    status=LeadStatus.NEW,
                    created_by=request.user,
                    import_batch=batch,
                )
                for _, cleaned in to_import
            )
            for lead in leads:
                lead.lead_code = lead_code_for(lead.pk)
            Lead.objects.bulk_update(leads, ["lead_code"])

            for (row, _), lead in zip(to_import, leads):
                row.result, row.lead = ImportRowResult.IMPORTED, lead
            ImportRow.objects.bulk_update(rows, ["result", "errors", "lead"])

            summary = batch_summary(batch)
            batch.status = ImportBatchStatus.COMPLETED
            batch.imported_at = timezone.now()
            batch.total_rows = summary["total_rows"]
            batch.successful_rows = summary["successful_rows"]
            batch.failed_rows = summary["failed_rows"]
            batch.duplicate_rows = summary["duplicate_rows"]
            batch.save()

        data = {
            "batch_id": str(batch.pk),
            "status": batch.status,
            "total_rows": batch.total_rows,
            "successful_rows": batch.successful_rows,
            "failed_rows": batch.failed_rows,
            "duplicate_rows": batch.duplicate_rows,
        }
        return success(data, f"{batch.successful_rows} lead(s) imported.")


class ImportCancelView(APIView):
    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, batch_id):
        with transaction.atomic():
            batch = get_object_or_404(ImportBatch.objects.select_for_update(), pk=batch_id)
            if batch.status != ImportBatchStatus.PREVIEW:
                raise Conflict(f"This import is already {batch.status}.")
            batch.status = ImportBatchStatus.CANCELLED
            batch.save(update_fields=["status", "updated_at"])
        return success({"batch_id": str(batch.pk), "status": batch.status}, "Import cancelled.")


class ImportReportView(APIView):
    """CSV of every invalid or skipped (duplicate) row: original columns + row_number, result, errors."""

    @extend_schema(responses={(200, "text/csv"): bytes})
    def get(self, request, batch_id):
        batch = get_object_or_404(ImportBatch, pk=batch_id)
        first = batch.rows.order_by("row_number").first()
        columns = list(first.data.keys()) if first else TEMPLATE_COLUMNS
        failed = batch.rows.filter(result__in=[ImportRowResult.INVALID, ImportRowResult.DUPLICATE]).order_by(
            "row_number"
        )

        def rows():
            for row in failed.iterator():
                errors = "; ".join(f"{e['field']}: {e['message']}" for e in row.errors)
                yield [row.data.get(c, "") for c in columns] + [row.row_number, row.result, errors]

        filename = f"bfs-import-report-{str(batch.pk)[:8]}.csv"
        return csv_download(filename, columns + ["row_number", "result", "errors"], rows())


@extend_schema(
    parameters=[OpenApiParameter("format", enum=["csv", "xlsx"], required=False)],
    responses={(200, "application/octet-stream"): bytes},
)
class ImportTemplateView(APIView):
    """Header row plus two sample rows. `service` accepts the category name or slug."""

    def get(self, request):
        file_format = (request.query_params.get("format") or "csv").lower()
        if file_format not in ("csv", "xlsx"):
            raise ValidationError({"format": ["Use csv or xlsx."]})
        examples = sample_rows()

        if file_format == "csv":
            return csv_download("bfs-lead-import-template.csv", TEMPLATE_COLUMNS, examples)

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Leads"
        sheet.append(TEMPLATE_COLUMNS)
        for example in examples:
            sheet.append(example)
        for cell in sheet["B"]:
            cell.number_format = "@"  # keep mobiles as text
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = content_disposition_header(True, "bfs-lead-import-template.xlsx")
        response["Cache-Control"] = "private, no-store"
        return response
