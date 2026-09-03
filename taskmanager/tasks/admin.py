from django.contrib import admin

from tasks.models import Comment, Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "status", "creator", "assignee", "due_date", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "description"]
    raw_id_fields = ["creator", "assignee"]
    readonly_fields = ["created_at", "updated_at", "completed_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "task", "author", "created_at"]
    search_fields = ["text"]
    raw_id_fields = ["task", "author"]
    readonly_fields = ["created_at", "updated_at"]
