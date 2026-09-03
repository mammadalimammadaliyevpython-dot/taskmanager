"""
The accounts API: one class per URL (routes are in accounts/urls.py).

Sign-in itself is djangorestframework-simplejwt's TokenObtainPairView / TokenRefreshView,
wired up directly in accounts/urls.py.
"""

from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny

from accounts.models import User
from accounts.serializers import RegisterSerializer, UserSerializer


@extend_schema_view(post=extend_schema(summary="Create an account"))
class RegisterView(generics.CreateAPIView):
    """POST /auth/register/ creates an account. Open to anyone; answers 201 with the user."""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer


@extend_schema_view(get=extend_schema(summary="The signed-in user"))
class MeView(generics.RetrieveAPIView):
    """GET /auth/me/ shows the signed-in user."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


@extend_schema_view(
    get=extend_schema(summary="Users to assign tasks to (?search= matches username or name)")
)
class UserListView(generics.ListAPIView):
    """GET /users/ lists active users, so a task can be assigned by id."""

    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = User.objects.filter(is_active=True).order_by("username")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return queryset
