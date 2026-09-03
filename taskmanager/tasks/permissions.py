"""Who may do what. Every endpoint already requires a signed-in user (settings.REST_FRAMEWORK)."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class TaskPermission(BasePermission):
    """
    Everyone signed in sees every task (the team shares one board).
    Editing, assigning, completing and reopening: the creator or the current assignee.
    Deleting: the creator only.
    """

    def has_object_permission(self, request, view, task):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return task.creator_id == request.user.id
        return request.user.id in (task.creator_id, task.assignee_id)


class CommentPermission(BasePermission):
    """Everyone signed in reads and adds comments; only the author edits or deletes one."""

    def has_object_permission(self, request, view, comment):
        return request.method in SAFE_METHODS or comment.author_id == request.user.id
