"""Shared test helpers: two users, a signed-in client and shortcuts to build data."""

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from tasks.models import Comment, Task

User = get_user_model()

PASSWORD = "correct-horse-battery"


# Every test creates users; the fast (insecure) hasher keeps the whole suite under a second.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ApiTestCase(APITestCase):
    """``self.client`` is signed in as ``self.user``; ``self.other`` is a second user."""

    def setUp(self):
        self.user = self.make_user("alice")
        self.other = self.make_user("bob")
        self.client.force_authenticate(self.user)

    @staticmethod
    def make_user(username, password=PASSWORD, **fields):
        fields.setdefault("first_name", username.title())
        return User.objects.create_user(username=username, password=password, **fields)

    @staticmethod
    def client_for(user):
        """A separate client signed in as another user, for permission tests."""
        client = APIClient()
        client.force_authenticate(user)
        return client

    def make_task(self, creator=None, **fields):
        fields.setdefault("title", "Write the report")
        return Task.objects.create(creator=creator or self.user, **fields)

    def make_comment(self, task, author=None, text="Looks good"):
        return Comment.objects.create(task=task, author=author or self.user, text=text)
