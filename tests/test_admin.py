from tests.helpers import BaseTestCase, TEST_PASSWORD
from pickaladder.models import User, Setting, Match, Friend
from pickaladder import db

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

    def test_toggle_email_verification(self):
        self.create_user(
            username="admin_toggle",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_toggle@example.com",
        )
        self.login("admin_toggle", TEST_PASSWORD)

        # Initial state
        setting = Setting(key="enforce_email_verification", value="true")
        db.session.add(setting)
        db.session.commit()

        response = self.app.post("/admin/toggle_email_verification", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email verification requirement has been disabled.", response.data)

        setting = db.session.get(Setting, "enforce_email_verification")
        self.assertEqual(setting.value, "false")

        # Toggle back
        response = self.app.post("/admin/toggle_email_verification", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email verification requirement has been enabled.", response.data)

        setting = db.session.get(Setting, "enforce_email_verification")
        self.assertEqual(setting.value, "true")

    def test_generate_users(self):
        self.create_user(
            username="admin_generate",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_generate@example.com",
        )
        self.login("admin_generate", TEST_PASSWORD)
        response = self.app.post("/admin/generate_users", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Generated Users", response.data)

        # Verify that new users have been created
        user_count = User.query.count()
        self.assertGreater(user_count, 1)

    def test_generate_matches(self):
        self.create_user(
            username="admin_matches",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_matches@example.com",
        )
        user2 = self.create_user(
            username="user2",
            password=TEST_PASSWORD,
            email="user2@example.com",
        )
        self.login("admin_matches", TEST_PASSWORD)
        admin = User.query.filter_by(username="admin_matches").first()

        # Create friendship
        friendship1 = Friend(user_id=admin.id, friend_id=user2.id, status="accepted")
        friendship2 = Friend(user_id=user2.id, friend_id=admin.id, status="accepted")
        db.session.add(friendship1)
        db.session.add(friendship2)
        db.session.commit()

        response = self.app.post("/admin/generate_matches", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"10 random matches generated successfully.", response.data)
        match_count = Match.query.count()
        self.assertGreater(match_count, 0)

    def test_reset_db(self):
        self.create_user(
            username="admin_reset",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_reset@example.com",
        )
        self.login("admin_reset", TEST_PASSWORD)
        response = self.app.post("/admin/reset_db", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Database has been reset.", response.data)
        user_count = User.query.count()
        self.assertEqual(user_count, 0)

    def test_reset_admin(self):
        self.create_user(
            username="admin_reset_admin",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_reset_admin@example.com",
        )
        user2 = self.create_user(
            username="user2_reset_admin",
            password=TEST_PASSWORD,
            is_admin=False,
            email="user2_reset_admin@example.com",
        )
        self.login("admin_reset_admin", TEST_PASSWORD)

        response = self.app.post("/admin/reset-admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin privileges have been reset.", response.data)

        admin_user = User.query.filter_by(username="admin_reset_admin").first()
        self.assertTrue(admin_user.is_admin)

        user2_user = User.query.filter_by(username="user2_reset_admin").first()
        self.assertFalse(user2_user.is_admin)

    def test_verify_user(self):
        self.create_user(
            username="admin_verify",
            password=TEST_PASSWORD,
            is_admin=True,
            email="admin_verify@example.com",
        )
        user_to_verify = self.create_user(
            username="user_to_verify",
            password=TEST_PASSWORD,
            email="user_to_verify@example.com",
            email_verified=False,
        )
        self.login("admin_verify", TEST_PASSWORD)

        response = self.app.post(f"/admin/verify_user/{user_to_verify.id}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"User user_to_verify has been manually verified.", response.data)

        verified_user = db.session.get(User, user_to_verify.id)
        self.assertTrue(verified_user.email_verified)
