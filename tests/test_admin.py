import unittest
from unittest.mock import patch, MagicMock

# Pre-emptive imports to ensure patch targets exist before the test runner looks for them.

from pickaladder import create_app
from tests.test_utils import mock_login_required

# Mock user payloads for consistent and readable tests
MOCK_ADMIN_ID = "admin_uid"
MOCK_ADMIN_PAYLOAD = {"uid": MOCK_ADMIN_ID, "email": "admin@example.com"}
MOCK_ADMIN_DATA = {"name": "Admin User", "isAdmin": True}

MOCK_USER_ID = "user_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user@example.com"}
MOCK_USER_DATA = {"name": "Regular User", "isAdmin": False}


class AdminRoutesFirebaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test client and a comprehensive mock environment for the admin routes."""
        self.mock_login_required = patch("pickaladder.admin.routes.login_required").start()
        # Create shared mocks to ensure consistent state across all patched modules.
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        # Define patchers for every location where the services are looked up.
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            # Patch for the `before_request` user loader in `__init__.py`.
            "init_firebase_admin": patch("pickaladder.firebase_admin"),
            "init_firestore": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            # Patch for the admin routes themselves.
            "admin_routes_auth": patch(
                "pickaladder.admin.routes.auth", new=self.mock_auth_service
            ),
            "admin_routes_firestore": patch(
                "pickaladder.admin.routes.firestore", new=self.mock_firestore_service
            ),
            # Patch for the login route, which can be a redirect target.
            "auth_routes_firestore": patch(
                "pickaladder.auth.routes.firestore", new=self.mock_firestore_service
            ),
        }

        # Start all patchers and register them for cleanup.
        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)
        self.addCleanup(self.mock_login_required.stop)

        # Configure the mock `firebase_admin` module used in `__init__.py`.
        self.mocks["init_firebase_admin"].auth = self.mock_auth_service

        # Create the Flask app *after* all patches are active.
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost",
                "LOGIN_DISABLED": True,
            }
        )
        self.client = self.app.test_client()

    def test_admin_panel_access_by_admin(self):
        """Test that an admin user can access the admin panel."""
        self.mock_login_required.side_effect = lambda *args, **kwargs: mock_login_required(admin_required=True)
        # The admin route also queries for the email verification setting. Mock this call.
        mock_settings_doc = self.mock_firestore_service.client.return_value.collection(
            "settings"
        ).document("enforceEmailVerification")
        mock_settings_doc.get.return_value.exists = False

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Panel", response.data)

    def test_admin_panel_access_denied_for_non_admin(self):
        """Test that a non-admin user is redirected from the admin panel."""
        with self.app.app_context():
            with patch("pickaladder.admin.routes.g") as mock_g:
                mock_g.user = {"uid": "test_user_id", "isAdmin": False}
                response = self.client.get("/admin/")
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.location)


if __name__ == "__main__":
    unittest.main()
