"""Private document storage: files live under PRIVATE_MEDIA_ROOT, which no URL route serves."""

import logging
import os
import uuid

import magic
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework.exceptions import ValidationError

from common.exceptions import FileTooLarge, UnsupportedFileType

logger = logging.getLogger(__name__)

# Extension -> MIME types libmagic may report for genuine files of that type.
ALLOWED_TYPES = {
    ".pdf": {"application/pdf", "application/x-pdf"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}
TYPE_ERROR = "Only PDF, JPG and PNG files are allowed."


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


def validate_document(upload):
    """Check extension, size and sniffed MIME type. Returns (extension, mime_type)."""
    extension = os.path.splitext(upload.name or "")[1].lower()
    if extension not in ALLOWED_TYPES:
        raise UnsupportedFileType(TYPE_ERROR)

    max_mb = settings.DOCUMENT_MAX_SIZE_MB
    if upload.size > max_mb * 1024 * 1024:
        raise FileTooLarge(f"Files must be {max_mb:g} MB or smaller.")
    if upload.size == 0:
        raise ValidationError({"file": ["The file is empty."]})

    head = upload.read(8192)
    upload.seek(0)
    mime_type = magic.from_buffer(head, mime=True)
    if mime_type not in ALLOWED_TYPES[extension]:
        raise UnsupportedFileType(f"The file content does not match its extension. {TYPE_ERROR}")
    return extension, mime_type


def save_document_file(lead_id, upload, extension):
    """Save under a random key, never the original filename. Returns the storage key."""
    key = f"leads/{lead_id}/{uuid.uuid4().hex}{extension}"
    return private_storage().save(key, upload)


def delete_document_file(storage_key):
    try:
        private_storage().delete(storage_key)
    except OSError:
        logger.exception("Could not delete document file %s", storage_key)
