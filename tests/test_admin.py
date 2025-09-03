from tests.helpers import BaseTestCase, create_user
from pickaladder.models import User


class AdminTestCase(BaseTestCase):
    def test_admin_panel_access_by_admin(self):
        create_user(
            username="admin_access",
            password="Password123!",
            is_admin=True,
            email="admin_access@example.com",
        )
        self.login("admin_access", "Password123!")
        response = self.app.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Panel", response.data)

    def test_admin_panel_access_by_non_admin(self):
        create_user(
            username="user_access",
            password="Password123!",
            email="user_access@example.com",
        )
        create_user(
            username="admin_non_access",
            password="Password123!",
            is_admin=True,
            email="admin_non_access@example.com",
        )
        self.login("user_access", "Password123!")
        response = self.app.get("/admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You are not authorized to view this page.", response.data)

    def test_generate_test_data(self):
        create_user(
            username="admin_generate",
            password="Password123!",
            is_admin=True,
            email="admin_generate@example.com",
        )
        self.login("admin_generate", "Password123!")
        response = self.app.get("/admin/generate_users", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Generated Users", response.data)

        # Verify that new users have been created
        user_count = User.query.count()
        self.assertGreater(user_count, 1)
        # Cannot test for matches as it's not guaranteed to be created.
        # match_count = Match.query.count()
        # self.assertGreater(match_count, 0)
