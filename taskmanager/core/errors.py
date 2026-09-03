"""
Error responses. Every error is JSON with a human ``detail`` and a machine-readable ``code``.

    {"detail": "Not found.", "code": "not_found"}

Field validation errors keep DRF's shape: {"title": ["This field is required."]}.
"""

from django.http import JsonResponse
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """DRF's standard handler plus a ``code`` field next to ``detail``."""
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        response.data["code"] = getattr(response.data["detail"], "code", "error")
    return response


# Django's own error pages, for URLs that match no route and for crashes, as JSON too.


def bad_request(request, exception=None):
    return JsonResponse({"detail": "Bad request", "code": "bad_request"}, status=400)


def forbidden(request, exception=None):
    return JsonResponse({"detail": "Forbidden", "code": "forbidden"}, status=403)


def not_found(request, exception=None):
    return JsonResponse({"detail": "Not found", "code": "not_found"}, status=404)


def server_error(request):
    return JsonResponse({"detail": "Internal server error", "code": "server_error"}, status=500)
