"""
Root URL configuration.

The API itself lives in each app's urls.py (core, accounts, tasks); this file adds the docs,
the admin and the JSON error handlers (Django only reads handler400/403/404/500 from here).
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularJSONAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

urlpatterns = [
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("tasks.urls")),
    path(
        "openapi.json",
        SpectacularJSONAPIView.as_view(),
        name="schema",
    ),
    path(
        "openapi.yaml",
        SpectacularYAMLAPIView.as_view(),
        name="schema-yaml",
    ),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="docs",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("admin/", admin.site.urls),
]

handler400 = "core.errors.bad_request"
handler403 = "core.errors.forbidden"
handler404 = "core.errors.not_found"
handler500 = "core.errors.server_error"
