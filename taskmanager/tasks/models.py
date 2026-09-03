"""Tasks and their comments."""

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    def with_related(self):
        """Everything the API shows for a task (both users, the comment count) in one query."""
        # Meta.ordering is ignored once a query groups (the Count), so order explicitly.
        return (
            self.select_related("creator", "assignee")
            .annotate(comment_count=Count("comments"))
            .order_by(*Task._meta.ordering)
        )


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO, db_index=True
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_tasks"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # a deleted user leaves the task unassigned
        related_name="assigned_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # completed_at follows the status: set when a task becomes done, cleared when reopened.
        if self.status != self.Status.DONE:
            self.completed_at = None
        elif self.completed_at is None:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]  # a conversation reads oldest first

    def __str__(self):
        return f"Comment {self.id} on task {self.task_id}"
