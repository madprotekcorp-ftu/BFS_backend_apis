import uuid

from django.conf import settings
from django.db import models

from common.choices import ImportBatchStatus, ImportRowResult
from common.models import TimeStampedModel


class ImportBatch(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=ImportBatchStatus.choices, default=ImportBatchStatus.PREVIEW, db_index=True
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    imported_at = models.DateTimeField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    successful_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "import batches"

    def __str__(self):
        return f"{self.filename} ({self.status})"


class ImportRow(TimeStampedModel):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField(help_text="Spreadsheet row; the header is row 1.")
    data = models.JSONField(default=dict)
    result = models.CharField(max_length=20, choices=ImportRowResult.choices, db_index=True)
    errors = models.JSONField(default=list, blank=True)
    lead = models.ForeignKey("leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["row_number"]
        constraints = [models.UniqueConstraint(fields=["batch", "row_number"], name="unique_import_row")]
