"""The tasks routes. Included at the root of taskmanager/urls.py."""

from django.urls import path

from tasks import views

urlpatterns = [
    path(
        "tasks/",
        views.TaskListCreateView.as_view(),
        name="task-list",
    ),
    path(
        "tasks/<int:pk>/",
        views.TaskDetailView.as_view(),
        name="task-detail",
    ),
    path(
        "tasks/<int:pk>/assign/",
        views.TaskAssignView.as_view(),
        name="task-assign",
    ),
    path(
        "tasks/<int:pk>/complete/",
        views.TaskCompleteView.as_view(),
        name="task-complete",
    ),
    path(
        "tasks/<int:pk>/reopen/",
        views.TaskReopenView.as_view(),
        name="task-reopen",
    ),
    path(
        "tasks/<int:task_pk>/comments/",
        views.CommentListCreateView.as_view(),
        name="comment-list",
    ),
    path(
        "tasks/<int:task_pk>/comments/<int:pk>/",
        views.CommentDetailView.as_view(),
        name="comment-detail",
    ),
]
