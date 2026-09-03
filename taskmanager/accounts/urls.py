"""The accounts routes. Included at the root of taskmanager/urls.py."""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts import views

urlpatterns = [
    path(
        "auth/register/",
        views.RegisterView.as_view(),
        name="register",
    ),
    path(
        "auth/token/",
        TokenObtainPairView.as_view(),
        name="token-obtain",
    ),
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "auth/me/",
        views.MeView.as_view(),
        name="me",
    ),
    path(
        "users/",
        views.UserListView.as_view(),
        name="user-list",
    ),
]
