from core.tests.base import ApiTestCase
from tasks.models import Comment


class CommentTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.task = self.make_task(creator=self.other)  # not our task: anyone may comment

    def test_add_a_comment(self):
        response = self.client.post(f"/tasks/{self.task.id}/comments/", {"text": "On it!"})
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(set(body), {"id", "task", "author", "text", "created_at", "updated_at"})
        self.assertEqual(body["task"], self.task.id)
        self.assertEqual(body["author"]["username"], "alice")
        self.assertEqual(body["text"], "On it!")
        self.assertEqual(self.client.get(f"/tasks/{self.task.id}/").json()["comment_count"], 1)

    def test_empty_text_is_400(self):
        for payload in [{}, {"text": ""}]:
            response = self.client.post(f"/tasks/{self.task.id}/comments/", payload)
            self.assertEqual(response.status_code, 400)
            self.assertIn("text", response.json())

    def test_list_is_oldest_first_and_paginated(self):
        first = self.make_comment(self.task, text="first")
        second = self.make_comment(self.task, author=self.other, text="second")
        self.make_comment(self.make_task(), text="elsewhere")
        response = self.client.get(f"/tasks/{self.task.id}/comments/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual([c["id"] for c in body["results"]], [first.id, second.id])
        self.assertEqual(body["results"][1]["author"]["username"], "bob")

    def test_unknown_task_is_404_for_list_and_create(self):
        self.assertEqual(self.client.get("/tasks/999/comments/").status_code, 404)
        self.assertEqual(self.client.post("/tasks/999/comments/", {"text": "x"}).status_code, 404)
        self.assertEqual(Comment.objects.count(), 0)

    def test_retrieve_only_through_its_own_task(self):
        comment = self.make_comment(self.task)
        other_task = self.make_task()
        self.assertEqual(
            self.client.get(f"/tasks/{self.task.id}/comments/{comment.id}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/tasks/{other_task.id}/comments/{comment.id}/").status_code, 404
        )

    def test_author_can_edit(self):
        comment = self.make_comment(self.task)
        response = self.client.patch(
            f"/tasks/{self.task.id}/comments/{comment.id}/", {"text": "edited"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "edited")

    def test_author_can_put(self):
        comment = self.make_comment(self.task)
        response = self.client.put(f"/tasks/{self.task.id}/comments/{comment.id}/", {"text": "new"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "new")
        self.assertEqual(
            self.client.put(f"/tasks/{self.task.id}/comments/{comment.id}/", {}).status_code, 400
        )

    def test_task_creator_cannot_edit_someone_elses_comment(self):
        comment = self.make_comment(self.task)  # by alice, on bob's task
        response = self.client_for(self.other).patch(
            f"/tasks/{self.task.id}/comments/{comment.id}/", {"text": "changed"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "permission_denied")

    def test_author_can_delete_and_others_cannot(self):
        comment = self.make_comment(self.task)
        url = f"/tasks/{self.task.id}/comments/{comment.id}/"
        self.assertEqual(self.client_for(self.other).delete(url).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comments_need_a_signed_in_user(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/tasks/{self.task.id}/comments/").status_code, 401)
