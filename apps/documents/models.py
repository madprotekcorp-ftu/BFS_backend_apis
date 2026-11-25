import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from common.choices import DocumentCategory
from common.models import TimeStampedModel


class LeadDocumentQuerySet(models.QuerySet):
    def visible(self):
        """Not in the bin, and the lead is not soft-deleted."""
        return self.filter(deleted_at__isnull=True, lead__is_deleted=False)

    def binned(self):
        return self.filter(deleted_at__isnull=False, lead__is_deleted=False)


class LeadDocument(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="documents")
    original_filename = models.CharField(max_length=255, help_text="Display only; never used as a path.")
    storage_key = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=20, choices=DocumentCategory.choices)
    file_size = models.PositiveIntegerField(help_text="Bytes")
    mime_type = models.CharField(max_length=100, help_text="Sniffed from the file content.")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = LeadDocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename
