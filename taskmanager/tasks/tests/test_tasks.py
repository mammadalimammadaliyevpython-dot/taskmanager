from core.tests.base import ApiTestCase
from tasks.models import Task

TASK_FIELDS = {
    "id",
    "title",
    "description",
    "status",
    "creator",
    "assignee",
    "due_date",
    "comment_count",
    "created_at",
    "updated_at",
    "completed_at",
}


class CreateTaskTests(ApiTestCase):
    def test_create_with_the_minimum(self):
        response = self.client.post("/tasks/", {"title": "Write the report"})
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(set(body), TASK_FIELDS)
        self.assertEqual(body["title"], "Write the report")
        self.assertEqual(body["description"], "")
        self.assertEqual(body["status"], "todo")
        self.assertEqual(body["creator"]["username"], "alice")
        self.assertIsNone(body["assignee"])
        self.assertIsNone(body["due_date"])
        self.assertIsNone(body["completed_at"])
        self.assertEqual(body["comment_count"], 0)
        self.assertEqual(Task.objects.get().creator, self.user)

    def test_create_with_everything(self):
        response = self.client.post(
            "/tasks/",
            {
                "title": "Ship it",
                "description": "Before Friday",
                "status": "in_progress",
                "assignee_id": self.other.id,
                "due_date": "2026-09-12",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], "in_progress")
        self.assertEqual(body["assignee"]["id"], self.other.id)
        self.assertEqual(body["assignee"]["username"], "bob")
        self.assertEqual(body["due_date"], "2026-09-12")

    def test_created_done_has_completed_at(self):
        response = self.client.post("/tasks/", {"title": "Already done", "status": "done"})
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.json()["completed_at"])

    def test_validation_errors(self):
        cases = [
            ({}, "title"),
            ({"title": ""}, "title"),
            ({"title": "x" * 201}, "title"),
            ({"title": "ok", "status": "later"}, "status"),
            ({"title": "ok", "assignee_id": 999}, "assignee_id"),
            ({"title": "ok", "due_date": "next week"}, "due_date"),
        ]
        for payload, field in cases:
            with self.subTest(payload=payload):
                response = self.client.post("/tasks/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertEqual(Task.objects.count(), 0)

    def test_creator_cannot_be_chosen(self):
        response = self.client.post("/tasks/", {"title": "Mine", "creator": self.other.id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["creator"]["id"], self.user.id)

    def test_inactive_user_cannot_be_assigned(self):
        gone = self.make_user("gone", is_active=False)
        response = self.client.post("/tasks/", {"title": "x", "assignee_id": gone.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("assignee_id", response.json())


class ListAndRetrieveTaskTests(ApiTestCase):
    def test_list_is_paginated_and_newest_first(self):
        first = self.make_task(title="First")
        second = self.make_task(title="Second", creator=self.other)
        response = self.client.get("/tasks/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"count", "next", "previous", "results"})
        self.assertEqual(body["count"], 2)
        self.assertEqual([task["id"] for task in body["results"]], [second.id, first.id])

    def test_everyone_sees_every_task(self):
        self.make_task(creator=self.other)
        self.assertEqual(self.client.get("/tasks/").json()["count"], 1)

    def test_retrieve(self):
        task = self.make_task(assignee=self.other)
        self.make_comment(task)
        response = self.client.get(f"/tasks/{task.id}/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], task.id)
        self.assertEqual(body["assignee"]["username"], "bob")
        self.assertEqual(body["comment_count"], 1)

    def test_unknown_task_is_404(self):
        response = self.client.get("/tasks/999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")

    def test_list_queries_do_not_grow_with_the_data(self):
        for number in range(5):
            task = self.make_task(title=f"Task {number}", assignee=self.other)
            self.make_comment(task)
        # one COUNT for the paginator, one SELECT for the page
        with self.assertNumQueries(2):
            response = self.client.get("/tasks/")
        self.assertEqual(response.json()["count"], 5)


class EditTaskTests(ApiTestCase):
    def test_creator_can_patch(self):
        task = self.make_task()
        response = self.client.patch(
            f"/tasks/{task.id}/", {"title": "Renamed", "assignee_id": self.other.id}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Renamed")
        self.assertEqual(response.json()["assignee"]["id"], self.other.id)

    def test_assignee_can_patch(self):
        task = self.make_task(creator=self.other, assignee=self.user)
        response = self.client.patch(f"/tasks/{task.id}/", {"description": "On it"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "On it")

    def test_bystander_cannot_patch(self):
        task = self.make_task(creator=self.other)
        response = self.client.patch(f"/tasks/{task.id}/", {"title": "Hijacked"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")
        task.refresh_from_db()
        self.assertEqual(task.title, "Write the report")

    def test_put_replaces(self):
        task = self.make_task(description="old", assignee=self.other)
        response = self.client.put(f"/tasks/{task.id}/", {"title": "New title"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["title"], "New title")
        # Only title is required; optional fields that are not sent keep their value (DRF).
        self.assertEqual(body["description"], "old")
        self.assertEqual(body["assignee"]["id"], self.other.id)
        self.assertEqual(self.client.put(f"/tasks/{task.id}/", {}).status_code, 400)

    def test_patch_status_moves_completed_at(self):
        task = self.make_task()
        done = self.client.patch(f"/tasks/{task.id}/", {"status": "done"}).json()
        self.assertIsNotNone(done["completed_at"])
        reopened = self.client.patch(f"/tasks/{task.id}/", {"status": "in_progress"}).json()
        self.assertIsNone(reopened["completed_at"])

    def test_patch_unassign_with_null(self):
        task = self.make_task(assignee=self.other)
        response = self.client.patch(f"/tasks/{task.id}/", {"assignee_id": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["assignee"])

    def test_read_only_fields_are_ignored(self):
        task = self.make_task()
        response = self.client.patch(
            f"/tasks/{task.id}/", {"completed_at": "2020-01-01T00:00:00Z", "id": 42}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], task.id)
        self.assertIsNone(response.json()["completed_at"])


class DeleteTaskTests(ApiTestCase):
    def test_creator_can_delete_and_comments_go_too(self):
        task = self.make_task()
        self.make_comment(task, author=self.other)
        response = self.client.delete(f"/tasks/{task.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(task.comments.count(), 0)

    def test_assignee_cannot_delete(self):
        task = self.make_task(creator=self.other, assignee=self.user)
        self.assertEqual(self.client.delete(f"/tasks/{task.id}/").status_code, 403)
        self.assertEqual(Task.objects.count(), 1)

    def test_delete_twice_is_404(self):
        task = self.make_task()
        self.client.delete(f"/tasks/{task.id}/")
        self.assertEqual(self.client.delete(f"/tasks/{task.id}/").status_code, 404)


class CompleteAndReopenTests(ApiTestCase):
    def test_complete_then_reopen(self):
        task = self.make_task()
        done = self.client.post(f"/tasks/{task.id}/complete/")
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(done.json()["status"], "done")
        self.assertIsNotNone(done.json()["completed_at"])

        reopened = self.client.post(f"/tasks/{task.id}/reopen/")
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["status"], "todo")
        self.assertIsNone(reopened.json()["completed_at"])

    def test_completing_twice_keeps_the_first_timestamp(self):
        task = self.make_task()
        first = self.client.post(f"/tasks/{task.id}/complete/").json()["completed_at"]
        second = self.client.post(f"/tasks/{task.id}/complete/").json()["completed_at"]
        self.assertEqual(first, second)

    def test_assignee_can_complete(self):
        task = self.make_task(creator=self.other, assignee=self.user)
        self.assertEqual(self.client.post(f"/tasks/{task.id}/complete/").status_code, 200)

    def test_bystander_cannot_complete(self):
        task = self.make_task(creator=self.other)
        response = self.client.post(f"/tasks/{task.id}/complete/")
        self.assertEqual(response.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)

    def test_unknown_task_is_404(self):
        self.assertEqual(self.client.post("/tasks/999/complete/").status_code, 404)


class AssignTests(ApiTestCase):
    def test_assign_and_unassign(self):
        task = self.make_task()
        response = self.client.post(
            f"/tasks/{task.id}/assign/", {"assignee_id": self.other.id}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["assignee"]["username"], "bob")

        response = self.client.post(
            f"/tasks/{task.id}/assign/", {"assignee_id": None}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["assignee"])

    def test_assignee_can_pass_the_task_on(self):
        carol = self.make_user("carol")
        task = self.make_task(creator=self.other, assignee=self.user)
        response = self.client.post(f"/tasks/{task.id}/assign/", {"assignee_id": carol.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assignee"]["username"], "carol")

    def test_bystander_cannot_assign(self):
        task = self.make_task(creator=self.other)
        response = self.client.post(f"/tasks/{task.id}/assign/", {"assignee_id": self.user.id})
        self.assertEqual(response.status_code, 403)

    def test_body_is_validated(self):
        task = self.make_task()
        for payload in [{}, {"assignee_id": 999}, {"assignee_id": "bob"}]:
            with self.subTest(payload=payload):
                response = self.client.post(f"/tasks/{task.id}/assign/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("assignee_id", response.json())


class ModelTests(ApiTestCase):
    def test_str(self):
        task = self.make_task(title="Buy milk")
        self.assertEqual(str(task), "Buy milk")
        comment = self.make_comment(task)
        self.assertEqual(str(comment), f"Comment {comment.id} on task {task.id}")

    def test_deleting_the_assignee_unassigns(self):
        task = self.make_task(assignee=self.other)
        self.other.delete()
        task.refresh_from_db()
        self.assertIsNone(task.assignee)

    def test_deleting_the_creator_deletes_the_task(self):
        self.make_task(creator=self.other)
        self.other.delete()
        self.assertEqual(Task.objects.count(), 0)
