"""Query-string filtering and ordering for GET /tasks/."""

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from tasks.models import Task

ORDERING_FIELDS = ["created_at", "updated_at", "due_date", "status", "title"]


def filter_tasks(queryset, params, user):
    """
    Apply the query parameters of a task list request.

    ?status=todo|in_progress|done, ?assignee=<id>|me|none, ?creator=<id>|me,
    ?search=<text> (title or description), ?ordering=<field> or -<field>
    (created_at, updated_at, due_date, status, title).
    Unknown values answer 400 with a message per parameter; absent ones are ignored.
    """
    errors = {}

    status = params.get("status")
    if status:
        if status in Task.Status.values:
            queryset = queryset.filter(status=status)
        else:
            errors["status"] = f"Choose one of: {', '.join(Task.Status.values)}"

    for field in ("assignee", "creator"):
        raw = params.get(field)
        if not raw:
            continue
        if raw == "me":
            queryset = queryset.filter(**{field: user})
        elif raw == "none" and field == "assignee":
            queryset = queryset.filter(assignee__isnull=True)
        elif raw.isdigit():
            queryset = queryset.filter(**{f"{field}_id": int(raw)})
        else:
            choices = "a user id, 'me' or 'none'" if field == "assignee" else "a user id or 'me'"
            errors[field] = f"Use {choices}"

    search = params.get("search")
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))

    ordering = params.get("ordering")
    if ordering:
        if ordering.lstrip("-") in ORDERING_FIELDS:
            queryset = queryset.order_by(ordering, "-id")
        else:
            errors["ordering"] = (
                f"Choose one of: {', '.join(ORDERING_FIELDS)} (prefix - to reverse)"
            )

    if errors:
        # same shape as field validation errors: a list of messages per parameter
        raise ValidationError({name: [message] for name, message in errors.items()})
    return queryset
