"""GET / (a map of the API) and GET /health/ (a dependency check). Both are open to anyone."""

from django.db import DatabaseError, connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from taskmanager import VERSION


class IndexView(APIView):
    """GET /: a short map of the API."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(summary="A short map of the API", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(
            {
                "service": "taskmanager",
                "version": VERSION,
                "docs": "/docs/",
                "endpoints": {
                    "/auth/register/": "POST create an account",
                    "/auth/token/": "POST username + password -> access and refresh tokens",
                    "/auth/token/refresh/": "POST refresh -> a new access token",
                    "/auth/me/": "GET the signed-in user",
                    "/users/": "GET users to assign tasks to",
                    "/tasks/": "GET list tasks (filterable); POST create a task",
                    "/tasks/{id}/": "GET one task; PATCH/PUT edit it; DELETE remove it",
                    "/tasks/{id}/assign/": "POST {assignee_id} assign (null to unassign)",
                    "/tasks/{id}/complete/": "POST mark the task done",
                    "/tasks/{id}/reopen/": "POST mark the task not done",
                    "/tasks/{id}/comments/": "GET comments; POST add one",
                    "/tasks/{id}/comments/{comment_id}/": "GET/PATCH/DELETE one comment",
                    "/health/": "GET liveness and database check",
                    "/docs/": "Swagger UI (also /redoc/, /openapi.json, /openapi.yaml)",
                },
            }
        )


class HealthView(APIView):
    """GET /health/: 200 when the database answers, 503 otherwise."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(summary="Health check", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = "ok"
        except DatabaseError:
            database = "error"
        healthy = database == "ok"
        body = {"status": "ok" if healthy else "degraded", "version": VERSION}
        body["checks"] = {"database": database}
        return Response(body, status=200 if healthy else 503)
