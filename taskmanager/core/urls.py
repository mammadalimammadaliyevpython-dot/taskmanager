"""The index and health routes. Included at the root of taskmanager/urls.py."""

from django.urls import path

from core import views

urlpatterns = [
    path(
        "",
        views.IndexView.as_view(),
        name="index",
    ),
    path(
        "health/",
        views.HealthView.as_view(),
        name="health",
    ),
]
