from accounts.models import User
from core.tests.base import PASSWORD, ApiTestCase


class RegisterTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(None)  # registration is anonymous

    def test_register_creates_a_user_and_hides_the_password(self):
        response = self.client.post(
            "/auth/register/",
            {"username": "carol", "password": PASSWORD, "email": "carol@example.com"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["username"], "carol")
        self.assertEqual(body["email"], "carol@example.com")
        self.assertNotIn("password", body)
        user = User.objects.get(username="carol")
        self.assertTrue(user.check_password(PASSWORD))

    def test_duplicate_username_is_400(self):
        response = self.client.post("/auth/register/", {"username": "alice", "password": PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_weak_password_is_400_on_the_password_field(self):
        response = self.client.post("/auth/register/", {"username": "carol", "password": "carol"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_missing_fields_are_400(self):
        response = self.client.post("/auth/register/", {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"username", "password"})


class TokenTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(None)

    def test_sign_in_refresh_and_use_the_token(self):
        response = self.client.post("/auth/token/", {"username": "alice", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        tokens = response.json()
        self.assertEqual(set(tokens), {"access", "refresh"})

        me = self.client.get("/auth/me/", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "alice")

        refreshed = self.client.post("/auth/token/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access", refreshed.json())

    def test_wrong_password_is_401(self):
        response = self.client.post("/auth/token/", {"username": "alice", "password": "nope"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "no_active_account")

    def test_me_without_a_token_is_401(self):
        response = self.client.get("/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")


class UserListTests(ApiTestCase):
    def test_lists_active_users_alphabetically(self):
        self.make_user("zed", is_active=False)
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual([user["username"] for user in body["results"]], ["alice", "bob"])
        self.assertEqual(set(body["results"][0]), {"id", "username", "first_name", "last_name"})

    def test_search_matches_username_or_name(self):
        self.make_user("carol", last_name="Bobbin")
        usernames = [
            user["username"] for user in self.client.get("/users/?search=bob").json()["results"]
        ]
        self.assertEqual(usernames, ["bob", "carol"])

    def test_requires_a_signed_in_user(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/users/").status_code, 401)
