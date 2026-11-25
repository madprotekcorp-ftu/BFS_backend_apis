import logging
import os

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.leads.views import get_active_lead
from common.exceptions import Conflict
from common.responses import no_content, success

from .models import LeadDocument
from .serializers import BinnedDocumentSerializer, DocumentSerializer, DocumentUploadSerializer
from .storage import delete_document_file, private_storage, save_document_file, validate_document

logger = logging.getLogger(__name__)


class LeadDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_lead(self):
        if not hasattr(self, "_lead"):
            self._lead = get_active_lead(self.kwargs["pk"])
        return self._lead

    def get_queryset(self):
        return (
            LeadDocument.objects.visible()
            .filter(lead=self.get_lead())
            .select_related("uploaded_by")
            .order_by("-uploaded_at")
        )

    @extend_schema(request={"multipart/form-data": DocumentUploadSerializer}, responses={201: DocumentSerializer})
    def post(self, request, *args, **kwargs):
        lead = self.get_lead()
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        extension, mime_type = validate_document(upload)

        storage_key = save_document_file(lead.pk, upload, extension)
        try:
            document = LeadDocument.objects.create(
                lead=lead,
                original_filename=os.path.basename(upload.name)[:255],
                storage_key=storage_key,
                category=serializer.validated_data["category"],
                file_size=upload.size,
                mime_type=mime_type,
                uploaded_by=request.user,
            )
        except Exception:
            delete_document_file(storage_key)
            raise
        return success(DocumentSerializer(document).data, "Document uploaded", status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    """Streams the file. Binned documents and documents of deleted leads return 404."""

    @extend_schema(
        parameters=[OpenApiParameter("inline", description="1 = open in the browser instead of downloading")],
        responses={(200, "application/octet-stream"): bytes},
    )
    def get(self, request, document_id):
        document = get_object_or_404(LeadDocument.objects.visible(), pk=document_id)
        inline = request.query_params.get("inline") in ("1", "true")

        if settings.DOCUMENTS_USE_X_ACCEL:
            # Django checked auth; Nginx serves the bytes from an `internal` location.
            response = HttpResponse(content_type=document.mime_type)
            response["X-Accel-Redirect"] = settings.DOCUMENTS_X_ACCEL_PREFIX + document.storage_key
        else:
            try:
                handle = private_storage().open(document.storage_key, "rb")
            except FileNotFoundError:
                logger.error("File missing for document %s", document.pk)
                raise NotFound()
            response = FileResponse(handle, content_type=document.mime_type)

        response["Content-Disposition"] = content_disposition_header(not inline, document.original_filename)
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class DocumentDeleteView(APIView):
    """Moves the document to the bin. The file stays in storage."""

    @extend_schema(responses={204: None})
    def delete(self, request, document_id):
        document = get_object_or_404(LeadDocument.objects.filter(lead__is_deleted=False), pk=document_id)
        if document.deleted_at is not None:
            raise Conflict("This document is already in the bin.")
        document.deleted_at = timezone.now()
        document.deleted_by = request.user
        document.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
        return no_content()


class DocumentBinListView(generics.ListAPIView):
    serializer_class = BinnedDocumentSerializer

    def get_queryset(self):
        return (
            LeadDocument.objects.binned()
            .select_related("lead", "uploaded_by", "deleted_by")
            .order_by("-deleted_at")
        )


class DocumentRestoreView(APIView):
    @extend_schema(request=None, responses=DocumentSerializer)
    def post(self, request, document_id):
        document = get_object_or_404(LeadDocument.objects.filter(lead__is_deleted=False), pk=document_id)
        if document.deleted_at is None:
            raise Conflict("This document is not in the bin.")
        document.deleted_at = None
        document.deleted_by = None
        document.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
        return success(DocumentSerializer(document).data, "Document restored")


class DocumentPurgeView(APIView):
    """Permanently deletes the record and the file. Only for documents in the bin."""

    @extend_schema(responses={204: None})
    def delete(self, request, document_id):
        document = get_object_or_404(LeadDocument.objects.filter(lead__is_deleted=False), pk=document_id)
        if document.deleted_at is None:
            raise Conflict("Only documents in the bin can be permanently deleted.")
        storage_key = document.storage_key
        with transaction.atomic():
            document.delete()
            transaction.on_commit(lambda: delete_document_file(storage_key))
        logger.info("Document %s purged by user %s", document_id, request.user.pk)
        return no_content()
