"""Custom API errors and the exception handler that renders the error envelope.

{ "success": false, "error": { "code": "...", "message": "...", "fields": {...} } }
"""

import logging
import math

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

VALIDATION_MESSAGE = "Please correct the highlighted fields."


class ApiError(exceptions.APIException):
    """An API error with a stable error code and optional extra keys in the error object."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request could not be completed."
    default_code = "bad_request"

    def __init__(self, detail=None, code=None, *, status_code=None, extra=None):
        super().__init__(detail=detail, code=code)
        if status_code is not None:
            self.status_code = status_code
        self.error_code = code or self.default_code
        self.extra = extra or {}


class Conflict(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action conflicts with the current state of the record."
    default_code = "conflict"


class FileTooLarge(ApiError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The file is too large."
    default_code = "file_too_large"


class UnsupportedFileType(ApiError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    default_detail = "This file type is not allowed."
    default_code = "unsupported_file_type"


def error_body(code, message, **extra):
    error = {"code": code, "message": message}
    error.update(extra)
    return {"success": False, "error": error}


def _validation_error(exc):
    detail = exc.detail
    if isinstance(detail, dict):
        fields = detail
    elif isinstance(detail, list):
        fields = {"non_field_errors": detail}
    else:
        fields = {"non_field_errors": [detail]}
    non_field = fields.get("non_field_errors")
    # A form-level error (e.g. wrong password) is the message itself.
    message = str(non_field[0]) if non_field and len(fields) == 1 else VALIDATION_MESSAGE
    return error_body("validation_error", message, fields=fields)


def _build_error(exc):
    if isinstance(exc, ApiError):
        return error_body(exc.error_code, str(exc.detail), **exc.extra)
    if isinstance(exc, exceptions.ValidationError):
        return _validation_error(exc)
    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return error_body("not_authenticated", "Please log in to continue.")
    if isinstance(exc, exceptions.PermissionDenied):
        if str(exc.detail).startswith("CSRF Failed"):
            return error_body(
                "csrf_failed", "Your security token is missing or expired. Refresh the page and try again."
            )
        return error_body("permission_denied", "You do not have permission to perform this action.")
    if isinstance(exc, exceptions.NotFound):
        return error_body("not_found", "The requested record was not found.")
    if isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait or 0)
        minutes = max(1, math.ceil(wait / 60))
        return error_body(
            "throttled",
            f"Too many attempts. Please try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            retry_after=wait,
        )
    code = exc.get_codes() if isinstance(exc.get_codes(), str) else exc.default_code
    return error_body(code, str(exc.detail))


def custom_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
    elif isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(detail=as_serializer_error(exc))

    response = drf_exception_handler(exc, context)
    if response is None:
        view = context.get("view")
        logger.exception("Unhandled error in %s", view.__class__.__name__ if view else "unknown view", exc_info=exc)
        return Response(
            error_body("server_error", "Something went wrong on our side. Please try again later."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    response.data = _build_error(exc)
    return response
