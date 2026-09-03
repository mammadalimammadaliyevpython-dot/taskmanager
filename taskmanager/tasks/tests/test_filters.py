from core.tests.base import ApiTestCase
from tasks.models import Task


class TaskFilterTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.todo = self.make_task(title="Write the report", assignee=self.other)
        self.doing = self.make_task(
            title="Review pull request",
            description="the report one",
            status=Task.Status.IN_PROGRESS,
            due_date="2026-09-10",
        )
        self.done = self.make_task(
            title="Deploy", creator=self.other, assignee=self.user, status=Task.Status.DONE
        )

    def ids(self, query):
        response = self.client.get(f"/tasks/?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return [task["id"] for task in response.json()["results"]]

    def test_status(self):
        self.assertEqual(self.ids("status=todo"), [self.todo.id])
        self.assertEqual(self.ids("status=done"), [self.done.id])
        self.assertEqual(self.ids("status="), [self.done.id, self.doing.id, self.todo.id])

    def test_assignee(self):
        self.assertEqual(self.ids("assignee=me"), [self.done.id])
        self.assertEqual(self.ids(f"assignee={self.other.id}"), [self.todo.id])
        self.assertEqual(self.ids("assignee=none"), [self.doing.id])

    def test_creator(self):
        self.assertEqual(self.ids("creator=me"), [self.doing.id, self.todo.id])
        self.assertEqual(self.ids(f"creator={self.other.id}"), [self.done.id])

    def test_search_matches_title_or_description(self):
        self.assertEqual(self.ids("search=REPORT"), [self.doing.id, self.todo.id])
        self.assertEqual(self.ids("search=nothing"), [])

    def test_ordering(self):
        self.assertEqual(self.ids("ordering=title"), [self.done.id, self.doing.id, self.todo.id])
        self.assertEqual(self.ids("ordering=-title"), [self.todo.id, self.doing.id, self.done.id])
        self.assertEqual(
            self.ids("ordering=created_at"), [self.todo.id, self.doing.id, self.done.id]
        )

    def test_filters_combine(self):
        self.assertEqual(self.ids("creator=me&status=in_progress"), [self.doing.id])
        self.assertEqual(self.ids("creator=me&status=done"), [])

    def test_bad_values_are_400_per_parameter(self):
        response = self.client.get("/tasks/?status=later&assignee=bob&creator=x&ordering=size")
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(set(body), {"status", "assignee", "creator", "ordering"})
        self.assertEqual(body["status"], ["Choose one of: todo, in_progress, done"])
        self.assertEqual(self.client.get("/tasks/?creator=none").status_code, 400)
