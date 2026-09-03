"""The tasks API: one view class per URL (routes are in tasks/urls.py)."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tasks.filters import filter_tasks
from tasks.models import Comment, Task
from tasks.permissions import CommentPermission, TaskPermission
from tasks.serializers import CommentSerializer, TaskAssignSerializer, TaskSerializer


@extend_schema_view(
    get=extend_schema(summary="List tasks", description=filter_tasks.__doc__),
    post=extend_schema(summary="Create a task"),
)
class TaskListCreateView(generics.ListCreateAPIView):
    """GET /tasks/ lists tasks, newest first (see tasks.filters). POST /tasks/ creates one."""

    serializer_class = TaskSerializer

    def get_queryset(self):
        return filter_tasks(
            Task.objects.with_related(), self.request.query_params, self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


@extend_schema_view(
    get=extend_schema(summary="One task"),
    put=extend_schema(summary="Replace a task (creator or assignee)"),
    patch=extend_schema(summary="Edit a task (creator or assignee)"),
    delete=extend_schema(summary="Delete a task and its comments (creator only)"),
)
class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET /tasks/<id>/ shows a task; PATCH/PUT edit it; DELETE removes it and its comments."""

    queryset = Task.objects.with_related()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, TaskPermission]


class TaskActionView(generics.GenericAPIView):
    """Base for the POST /tasks/<id>/<action>/ endpoints: loads the task, checks permissions."""

    queryset = Task.objects.with_related()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, TaskPermission]

    def update_status(self, status):
        task = self.get_object()
        task.status = status
        task.save()
        return Response(TaskSerializer(task).data)


class TaskCompleteView(TaskActionView):
    """POST /tasks/<id>/complete/ marks the task done (sets completed_at)."""

    @extend_schema(summary="Mark a task done", request=None, responses={200: TaskSerializer})
    def post(self, request, pk):
        return self.update_status(Task.Status.DONE)


class TaskReopenView(TaskActionView):
    """POST /tasks/<id>/reopen/ puts a done task back to "to do"."""

    @extend_schema(summary="Reopen a task", request=None, responses={200: TaskSerializer})
    def post(self, request, pk):
        return self.update_status(Task.Status.TODO)


class TaskAssignView(TaskActionView):
    """POST /tasks/<id>/assign/ with {"assignee_id": <user id> | null}."""

    @extend_schema(
        summary="Assign a task to a user (null to unassign)",
        request=TaskAssignSerializer,
        responses={200: TaskSerializer},
    )
    def post(self, request, pk):
        task = self.get_object()
        form = TaskAssignSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        task.assignee = form.validated_data["assignee"]
        task.save()
        return Response(TaskSerializer(task).data)


@extend_schema_view(
    get=extend_schema(summary="List a task's comments, oldest first"),
    post=extend_schema(summary="Comment on a task"),
)
class CommentListCreateView(generics.ListCreateAPIView):
    """GET /tasks/<id>/comments/ lists a task's comments, oldest first. POST adds one."""

    serializer_class = CommentSerializer

    def get_queryset(self):
        task = get_object_or_404(Task, pk=self.kwargs["task_pk"])
        return task.comments.select_related("author")

    def perform_create(self, serializer):
        task = get_object_or_404(Task, pk=self.kwargs["task_pk"])
        serializer.save(task=task, author=self.request.user)


@extend_schema_view(
    get=extend_schema(summary="One comment"),
    put=extend_schema(summary="Replace a comment (author only)"),
    patch=extend_schema(summary="Edit a comment (author only)"),
    delete=extend_schema(summary="Delete a comment (author only)"),
)
class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET /tasks/<id>/comments/<comment_id>/ shows one comment; PATCH/PUT and DELETE: author."""

    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, CommentPermission]

    def get_queryset(self):
        return Comment.objects.filter(task_id=self.kwargs["task_pk"]).select_related("author")
