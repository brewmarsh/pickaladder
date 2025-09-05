from tests.helpers import BaseTestCase, TEST_PASSWORD
from pickaladder.models import User


class AdminTestCase(BaseTestCase):
    def test_admin_panel_access_by_admin(self):
        self.create_user(
            username="admin_access",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_access@example.com",
        )
        self.login("admin_access", TEST_PASSWORD)
        response = self.app.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Panel", response.data)

    def test_admin_panel_access_by_non_admin(self):
        self.create_user(
            username="user_access",
            password=TEST_PASSWORD,
            email="user_access@example.com",
        )
        self.create_user(
            username="admin_non_access",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_non_access@example.com",
        )
        self.login("user_access", TEST_PASSWORD)
        response = self.app.get("/admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You are not authorized to view this page.", response.data)

    def test_generate_test_data(self):
        self.create_user(
            username="admin_generate",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_generate@example.com",
        )
        self.login("admin_generate", TEST_PASSWORD)
        response = self.app.get("/admin/generate_users", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Generated Users", response.data)

        # Verify that new users have been created
        user_count = User.query.count()
        self.assertGreater(user_count, 1)
        # Cannot test for matches as it's not guaranteed to be created.
        # match_count = Match.query.count()
        # self.assertGreater(match_count, 0)
