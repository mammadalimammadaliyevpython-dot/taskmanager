"""What the tasks API sends and accepts."""

from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer
from tasks.models import Comment, Task


class TaskSerializer(serializers.ModelSerializer):
    """
    A task. Users are embedded on the way out; on the way in, ``assignee_id`` takes a user id
    (or null to unassign). The creator is always the signed-in user.
    """

    creator = UserSerializer(read_only=True)
    assignee = UserSerializer(read_only=True)
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.filter(is_active=True),
        allow_null=True,
        required=False,
        write_only=True,
        help_text="Id of the user to assign the task to; null to unassign",
    )
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "creator",
            "assignee",
            "assignee_id",
            "due_date",
            "comment_count",
            "created_at",
            "updated_at",
            "completed_at",
        ]

    def get_comment_count(self, task) -> int:
        # Annotated by TaskQuerySet.with_related(); a task that was just created has none yet.
        count = getattr(task, "comment_count", None)
        return task.comments.count() if count is None else count


class TaskAssignSerializer(serializers.Serializer):
    """The body of POST /tasks/<id>/assign/."""

    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.filter(is_active=True),
        allow_null=True,
        help_text="Id of the user to assign the task to; null to unassign",
    )


class CommentSerializer(serializers.ModelSerializer):
    """A comment. The task comes from the URL and the author is the signed-in user."""

    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "task", "author", "text", "created_at", "updated_at"]
        read_only_fields = ["task"]
