from django.contrib.auth import get_user_model
from django.test import override_settings

from core.tests.base import PASSWORD, ApiTestCase
from tasks.models import Task


class IndexAndHealthTests(ApiTestCase):
    def test_index_is_public_and_lists_the_endpoints(self):
        self.client.force_authenticate(None)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["service"], "taskmanager")
        self.assertIn("/tasks/", body["endpoints"])
        self.assertEqual(body["docs"], "/docs/")

    def test_health_is_public(self):
        self.client.force_authenticate(None)
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["checks"], {"database": "ok"})


class ErrorFormatTests(ApiTestCase):
    def test_unknown_url_is_json_404(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found", "code": "not_found"})

    def test_wrong_method_carries_a_code(self):
        response = self.client.put("/health/")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["code"], "method_not_allowed")

    def test_anonymous_request_is_401_with_a_code(self):
        self.client.force_authenticate(None)
        response = self.client.get("/tasks/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_bad_token_is_401_with_a_code(self):
        self.client.force_authenticate(None)
        response = self.client.get("/tasks/", HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "token_not_valid")


class PaginationTests(ApiTestCase):
    def test_page_size_is_capped_by_the_setting(self):
        for number in range(5):
            self.make_task(title=f"Task {number}")
        with override_settings(TASKMANAGER_PAGE_SIZE=2, TASKMANAGER_MAX_PAGE_SIZE=3):
            default = self.client.get("/tasks/").json()
            self.assertEqual(default["count"], 5)
            self.assertEqual(len(default["results"]), 2)
            self.assertIn("page=2", default["next"])
            capped = self.client.get("/tasks/?page_size=50").json()
            self.assertEqual(len(capped["results"]), 3)
            last = self.client.get("/tasks/?page=3").json()
            self.assertEqual(len(last["results"]), 1)
            self.assertIsNone(last["next"])

    def test_page_past_the_end_is_404(self):
        response = self.client.get("/tasks/?page=99")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")


class DocsTests(ApiTestCase):
    def test_openapi_schema_is_public_and_complete(self):
        self.client.force_authenticate(None)
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(schema["info"]["title"], "Task manager API")
        for path in [
            "/auth/register/",
            "/auth/token/",
            "/auth/token/refresh/",
            "/auth/me/",
            "/users/",
            "/tasks/",
            "/tasks/{id}/",
            "/tasks/{id}/assign/",
            "/tasks/{id}/complete/",
            "/tasks/{id}/reopen/",
            "/tasks/{task_pk}/comments/",
            "/tasks/{task_pk}/comments/{id}/",
            "/health/",
        ]:
            self.assertIn(path, schema["paths"], path)
        self.assertIn("jwtAuth", schema["components"]["securitySchemes"])

    def test_docs_pages_render(self):
        self.client.force_authenticate(None)
        for path in ["/docs/", "/redoc/", "/openapi.yaml"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)


class AdminTests(ApiTestCase):
    """Every admin screen (Jazzmin theme) renders for a superuser: list, add, change, delete."""

    def setUp(self):
        super().setUp()
        get_user_model().objects.create_superuser("root", "root@example.com", PASSWORD)
        self.task = self.make_task(assignee=self.other)
        self.comment = self.make_comment(self.task)
        self.client.force_authenticate(None)
        self.assertTrue(self.client.login(username="root", password=PASSWORD))

    def assert_page(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200, path)
        self.assertIn(b"jazzmin", response.content, path)  # the theme is active
        return response

    def test_login_page_and_index(self):
        self.client.logout()
        self.assert_page("/admin/login/")
        self.assertEqual(self.client.get("/admin/").status_code, 302)  # to the login page
        self.client.login(username="root", password=PASSWORD)
        index = self.assert_page("/admin/")
        for label in [b"Task manager", b"Tasks", b"Comments", b"Users", b"API docs"]:
            self.assertIn(label, index.content)

    def test_every_model_screen(self):
        instances = {
            "tasks/task": self.task,
            "tasks/comment": self.comment,
            "accounts/user": self.user,
        }
        for prefix, instance in instances.items():
            with self.subTest(model=prefix):
                self.assert_page(f"/admin/{prefix}/")
                self.assert_page(f"/admin/{prefix}/", q="alice")
                self.assert_page(f"/admin/{prefix}/add/")
                self.assert_page(f"/admin/{prefix}/{instance.pk}/change/")
                self.assert_page(f"/admin/{prefix}/{instance.pk}/delete/")
                self.assert_page(f"/admin/{prefix}/{instance.pk}/history/")
        self.assert_page("/admin/tasks/task/", status__exact="todo")
        self.assert_page("/admin/tasks/")
        self.assert_page("/admin/accounts/")
        self.assert_page("/admin/auth/group/")
        self.assert_page("/admin/auth/group/add/")
        self.assert_page("/admin/password_change/")
        self.assertEqual(self.client.get("/admin/jsi18n/").status_code, 200)

    def test_global_search(self):
        response = self.client.post("/admin/tasks/task/", {"q": "report"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Write the report", response.content)

    def test_create_edit_and_delete_through_the_admin(self):
        response = self.client.post(
            "/admin/tasks/task/add/",
            {
                "title": "From the admin",
                "description": "",
                "status": "done",
                "creator": self.user.pk,
                "assignee": "",
                "due_date": "",
            },
        )
        self.assertEqual(response.status_code, 302, response.content[:500])
        created = Task.objects.get(title="From the admin")
        self.assertIsNotNone(created.completed_at)  # the model's save() logic runs here too

        response = self.client.post(
            f"/admin/tasks/task/{created.pk}/change/",
            {
                "title": "From the admin",
                "description": "",
                "status": "todo",
                "creator": self.user.pk,
                "assignee": self.other.pk,
                "due_date": "2026-09-12",
            },
        )
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertIsNone(created.completed_at)
        self.assertEqual(created.assignee, self.other)

        response = self.client.post(f"/admin/tasks/task/{created.pk}/delete/", {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Task.objects.filter(pk=created.pk).exists())

    def test_bulk_delete_action(self):
        response = self.client.post(
            "/admin/tasks/comment/",
            {"action": "delete_selected", "_selected_action": [self.comment.pk], "post": "yes"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.task.comments.count(), 0)

    def test_logout(self):
        response = self.client.post("/admin/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_staff_only(self):
        self.client.logout()
        self.client.login(username="alice", password=PASSWORD)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)  # bounced to the login page
