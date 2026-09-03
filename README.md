# Task manager API

A small HTTP API for managing a team's tasks: create, edit and delete tasks, assign them to
other users, mark them done, and discuss them in comments. Sign-in is by JWT, the API is
documented with Swagger, the Django admin (Jazzmin theme) is there for housekeeping, and
everything is stored in SQLite so a restart loses nothing.
Python 3.11+, Django 5.2 LTS, Django REST Framework.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd taskmanager
python manage.py migrate
python manage.py runserver
```

The API is now on http://127.0.0.1:8000, with interactive docs at http://127.0.0.1:8000/docs/.
The SQLite database lands in `taskmanager/data/`; delete that directory to start from scratch.

Prefer Docker? `docker compose up --build` does the same on http://127.0.0.1:8000 with a
named volume for the data.

## Try it with curl

Run these from a second terminal with the server started as above. Every URL ends with a
slash (Django's convention). Authenticated requests carry `Authorization: Bearer <access>`.

```bash
# 1. register two users (open to anyone)
curl -s -X POST localhost:8000/auth/register/ -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "correct-horse-battery", "first_name": "Alice"}'
# {"id": 1, "username": "alice", "email": "", "first_name": "Alice", "last_name": ""}
curl -s -X POST localhost:8000/auth/register/ -H 'Content-Type: application/json' \
  -d '{"username": "bob", "password": "correct-horse-battery", "first_name": "Bob"}'

# 2. sign in: a JWT access token (1 hour) and a refresh token (7 days)
curl -s -X POST localhost:8000/auth/token/ -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "correct-horse-battery"}'
# {"refresh": "eyJ...", "access": "eyJ..."}
export TOKEN=<the access token>
curl -s localhost:8000/auth/me/ -H "Authorization: Bearer $TOKEN"
# {"id": 1, "username": "alice", "first_name": "Alice", "last_name": ""}

# 3. who can I assign tasks to?
curl -s localhost:8000/users/ -H "Authorization: Bearer $TOKEN"
# {"count": 2, "next": null, "previous": null, "results": [{"id": 1, "username": "alice", ...}, {"id": 2, "username": "bob", ...}]}

# 4. create a task (only title is required)
curl -s -X POST localhost:8000/tasks/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title": "Write the report", "description": "Q3 numbers", "due_date": "2026-09-12"}'
# {"id": 1, "title": "Write the report", "description": "Q3 numbers", "status": "todo",
#  "creator": {"id": 1, "username": "alice", "first_name": "Alice", "last_name": ""},
#  "assignee": null, "due_date": "2026-09-12", "comment_count": 0,
#  "created_at": "2026-09-03T05:56:03.248607Z", "updated_at": "2026-09-03T05:56:03.248626Z", "completed_at": null}

# 5. assign it to bob (null unassigns)
curl -s -X POST localhost:8000/tasks/1/assign/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"assignee_id": 2}'
# {... "assignee": {"id": 2, "username": "bob", "first_name": "Bob", "last_name": ""} ...}

# 6. edit it (PATCH takes any subset of title, description, status, assignee_id, due_date)
curl -s -X PATCH localhost:8000/tasks/1/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status": "in_progress"}'

# 7. comment on it
curl -s -X POST localhost:8000/tasks/1/comments/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"text": "Draft is in the shared folder"}'
# {"id": 1, "task": 1, "author": {"id": 1, "username": "alice", ...}, "text": "Draft is in the shared folder",
#  "created_at": "2026-09-03T05:56:03.564871Z", "updated_at": "2026-09-03T05:56:03.564891Z"}
curl -s localhost:8000/tasks/1/comments/ -H "Authorization: Bearer $TOKEN"

# 8. mark it done (the creator or the assignee may)
curl -s -X POST localhost:8000/tasks/1/complete/ -H "Authorization: Bearer $TOKEN"
# {... "status": "done", "comment_count": 1, "completed_at": "2026-09-03T05:56:03.734148Z"}

# 9. list and filter: ?status=, ?assignee=<id>|me|none, ?creator=<id>|me, ?search=, ?ordering=
curl -s "localhost:8000/tasks/?status=done&assignee=2" -H "Authorization: Bearer $TOKEN"
# {"count": 1, "next": null, "previous": null, "results": [ ... ]}

# 10. delete it (creator only); the comments go with it
curl -s -X DELETE -w '%{http_code}\n' localhost:8000/tasks/1/ -H "Authorization: Bearer $TOKEN"
# 204

# 11. restart the server (Ctrl-C, python manage.py runserver): users and tasks are still there
curl -s localhost:8000/tasks/ -H "Authorization: Bearer $TOKEN"
```

Or skip the typing: open http://127.0.0.1:8000/docs/, call `/auth/token/` from the page,
press **Authorize** and paste the access token. Every endpoint can then be tried from the browser.

`scripts/smoke.sh` runs this whole sequence, including the restart, against a private server
and fails loudly if anything is off. `make smoke` is the same thing.

## API

Interactive documentation: `/docs/` (Swagger UI) and `/redoc/`; the schema itself is at
`/openapi.json` and `/openapi.yaml`.

| Method | Path | What it does | Success |
|---|---|---|---|
| `POST` | `/auth/register/` | Create an account: `username`, `password`, optional `email`, `first_name`, `last_name` | `201` user |
| `POST` | `/auth/token/` | `username` + `password` -> `{access, refresh}` | `200` |
| `POST` | `/auth/token/refresh/` | `refresh` -> a new `access` | `200` |
| `GET` | `/auth/me/` | The signed-in user | `200` user |
| `GET` | `/users/?search=` | Active users, alphabetically; search matches username or name | `200` page of users |
| `GET` | `/tasks/` | Tasks, newest first; see filters below | `200` page of tasks |
| `POST` | `/tasks/` | Create a task: `title`, optional `description`, `status`, `assignee_id`, `due_date` | `201` task |
| `GET` | `/tasks/{id}/` | One task | `200` task |
| `PATCH` / `PUT` | `/tasks/{id}/` | Edit a task (creator or assignee) | `200` task |
| `DELETE` | `/tasks/{id}/` | Delete a task and its comments (creator only) | `204` |
| `POST` | `/tasks/{id}/assign/` | `{"assignee_id": 2}` or `{"assignee_id": null}` (creator or assignee) | `200` task |
| `POST` | `/tasks/{id}/complete/` | Mark done; sets `completed_at` (creator or assignee) | `200` task |
| `POST` | `/tasks/{id}/reopen/` | Back to `todo`; clears `completed_at` (creator or assignee) | `200` task |
| `GET` | `/tasks/{id}/comments/` | The task's comments, oldest first | `200` page of comments |
| `POST` | `/tasks/{id}/comments/` | `{"text": "..."}` (anyone signed in) | `201` comment |
| `GET` | `/tasks/{id}/comments/{comment_id}/` | One comment | `200` comment |
| `PATCH` / `PUT` | `/tasks/{id}/comments/{comment_id}/` | Edit a comment (author only) | `200` comment |
| `DELETE` | `/tasks/{id}/comments/{comment_id}/` | Delete a comment (author only) | `204` |
| `GET` | `/health/` | Database check | `200`, or `503` when degraded |
| `GET` | `/` | A short map of the API | `200` |

A task's `status` is `todo`, `in_progress` or `done`. Setting it to `done` (by PATCH or
`/complete/`) stamps `completed_at`; anything else clears it. The `creator` is always the user
who made the task; on the way out both `creator` and `assignee` are embedded user objects, on
the way in `assignee_id` takes a user id.

Lists are paginated: `?page=2&page_size=50` and a `{count, next, previous, results}` envelope.

`GET /tasks/` filters, all optional and combinable:

| Parameter | Values |
|---|---|
| `status` | `todo`, `in_progress`, `done` |
| `assignee` | a user id, `me`, or `none` for unassigned tasks |
| `creator` | a user id or `me` |
| `search` | text matched against title and description, case-insensitive |
| `ordering` | `created_at`, `updated_at`, `due_date`, `status`, `title`; prefix `-` to reverse (default: newest first) |

`/admin/` is Django's admin with the [Jazzmin](https://github.com/farridav/django-jazzmin)
theme, useful for browsing and bulk-editing users, tasks and comments. Create an account
with `python manage.py createsuperuser` (or `make superuser`) and sign in at
http://127.0.0.1:8000/admin/. It is not part of the API.

### Authentication

JWT (djangorestframework-simplejwt). Everything except `/`, `/health/`, `/auth/register/`,
`/auth/token/`, `/auth/token/refresh/` and the docs requires `Authorization: Bearer <access>`.
Access tokens last an hour and refresh tokens a week by default (both configurable). There
are no roles: every signed-in user sees every task; who may change what is in the table above.

### Errors

Errors are JSON. Everything except validation errors carries a human `detail` and a
machine-readable `code`:

| Status | `code` | When |
|---|---|---|
| `400` | (field errors) | Invalid input: `{"title": ["This field is required."]}`, `{"status": ["Choose one of: todo, in_progress, done"]}` |
| `401` | `not_authenticated` | No token sent |
| `401` | `token_not_valid` | The token is expired or malformed |
| `401` | `no_active_account` | Wrong username or password at `/auth/token/` |
| `403` | `permission_denied` | Signed in, but not the creator/assignee (tasks) or author (comments) |
| `404` | `not_found` | Unknown task, comment, page or URL |
| `405` | `method_not_allowed` | e.g. `PUT /tasks/` |

## Configuration

All settings are environment variables with working defaults (see `.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `TASKMANAGER_DATA_DIR` | `taskmanager/data` | Directory for the SQLite database |
| `TASKMANAGER_PAGE_SIZE` | `20` | Page size when `page_size` is absent |
| `TASKMANAGER_MAX_PAGE_SIZE` | `100` | Largest page size a client may ask for |
| `TASKMANAGER_ACCESS_TOKEN_MINUTES` | `60` | JWT access token lifetime |
| `TASKMANAGER_REFRESH_TOKEN_DAYS` | `7` | JWT refresh token lifetime |
| `TASKMANAGER_SECRET_KEY` | a dev key | Django's secret key (also signs the JWTs); set a long random value on servers |
| `TASKMANAGER_DEBUG` | `false` | Django debug mode (never on servers) |
| `TASKMANAGER_ALLOWED_HOSTS` | `*` | Comma-separated hostnames Django will serve |
| `TASKMANAGER_LOG_LEVEL` | `INFO` | Log level for the console logger |
| `TASKMANAGER_MIGRATE_ON_START` | `true` | Container only: run migrations before starting gunicorn |
| `WEB_CONCURRENCY` | `4` | Container only: gunicorn worker count |

## Tests

```bash
pip install -r requirements-dev.txt   # adds coverage and ruff
make test        # the whole suite, a few seconds   (or: cd taskmanager && python manage.py test)
make coverage    # same, with a coverage report (fails under 90%)
make lint        # ruff check + format check
make smoke       # curl walkthrough against a real server, with a restart
```

`make help` lists every target; `make package` builds `taskmanager.zip` for sharing.

The tests live next to the code they cover: `accounts/tests.py` (registration, tokens, the
user directory), `tasks/tests/` (every task and comment endpoint, permissions, filters,
ordering, query counts) and `core/tests/` (errors, pagination, the OpenAPI schema, the docs
pages, every admin screen). Line coverage is about 98%. CI (`.github/workflows/ci.yml`) runs
lint, tests, the smoke script and a Docker build.

## Project layout

```
taskmanager/                         Django project (run manage.py from here)
  manage.py
  taskmanager/settings.py            generated settings + TASKMANAGER_* environment handling, Jazzmin
  taskmanager/urls.py                includes each app's urls, adds docs, admin, JSON error handlers
  accounts/                          users
    models.py                        User (Django's AbstractUser under our own name)
    admin.py                         admin registration (same in tasks/)
    serializers.py                   UserSerializer, RegisterSerializer
    views.py                         RegisterView, MeView, UserListView
    urls.py                          /auth/*, /users/ (JWT views come from simplejwt)
  tasks/                             tasks and comments
    models.py                        Task, Comment
    serializers.py                   input/output shapes
    permissions.py                   who may edit, delete, complete, comment
    filters.py                       ?status= ?assignee= ?creator= ?search= ?ordering=
    views.py                         one view class per URL
    urls.py                          /tasks/*
  core/                              shared plumbing
    pagination.py                    page/page_size paging for every list
    errors.py                        JSON errors with a `code`
    views.py                         IndexView (/), HealthView (/health/)
    tests/base.py                    shared test helpers
scripts/smoke.sh                     end-to-end curl check with restart
scripts/package.sh                   builds taskmanager.zip for sharing
Makefile, Dockerfile, docker-compose.yml, .github/workflows/ci.yml, pyproject.toml (ruff)
```

## Decisions and assumptions

- **Django + DRF generic views.** The brief asks for Django REST Framework. CRUD endpoints are
  DRF generic views (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`); the three actions
  (`assign`, `complete`, `reopen`) are small `GenericAPIView` subclasses so they reuse the
  same object lookup and permission checks. Every view is named `...View` and lives in its
  app's `views.py`, with routes in that app's `urls.py`.
- **Explicit action endpoints plus plain PATCH.** Assigning and completing are the two
  operations the brief names, so they get their own URLs with a clear contract. `PATCH` with
  `assignee_id` or `status` does the same thing; both paths go through the model, so
  `completed_at` is always right.
- **Permissions.** A shared team board: everyone signed in sees everything. Changing a task
  is for its creator or its current assignee, deleting for the creator only, and a comment
  belongs to its author. There is no admin role in the API; the Django admin covers that.
- **JWT over sessions.** The brief suggests JWT or OAuth 2.0; simplejwt is the standard DRF
  choice, needs no extra infrastructure and works with plain curl. Registration is open so
  reviewers can create users without the admin.
- **SQLite.** Zero setup for reviewers; WAL mode and a busy timeout make it fine for a small
  team behind gunicorn. Switching to PostgreSQL is a `DATABASES` change plus `psycopg`.
- **Custom user model** that adds nothing yet, because Django recommends starting with one:
  adding fields later is then a normal migration.
- **Deletion is real.** Deleting a task removes its comments; deleting a user removes their
  tasks and comments and unassigns them from others' tasks.
- **Paths end with a slash**, Django's convention. `/tasks` without the slash answers a
  `301` to `/tasks/`, which curl does not follow unless told to, so type the slash.

## Ideas for later

1. Roles (project admins who can edit or delete any task) and per-project boards with
   membership, so not everyone sees everything.
2. Notifications: e-mail or webhook when you are assigned a task or someone comments on yours.
3. Richer tasks: priority, labels, attachments, a history of status changes, subtasks.
4. Soft delete with an undo window instead of hard deletion.
5. PostgreSQL and a proper deployment (nginx in front of gunicorn, a secret key from the
   environment, `SECURE_*` settings behind TLS).
