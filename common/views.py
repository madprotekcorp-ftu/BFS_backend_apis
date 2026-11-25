"""JSON versions of Django's error pages (used when DEBUG is off)."""

from django.http import JsonResponse

from .exceptions import error_body


def bad_request(request, exception=None):
    return JsonResponse(error_body("bad_request", "Bad request."), status=400)


def permission_denied(request, exception=None):
    return JsonResponse(error_body("permission_denied", "You do not have permission to perform this action."), status=403)


def not_found(request, exception=None):
    return JsonResponse(error_body("not_found", "The requested resource was not found."), status=404)


def server_error(request):
    return JsonResponse(
        error_body("server_error", "Something went wrong on our side. Please try again later."), status=500
    )
