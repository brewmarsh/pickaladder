import unittest
from unittest.mock import patch, MagicMock

# Pre-emptive imports to ensure patch targets exist before the test runner looks for them.

from pickaladder import create_app

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

        # Configure the mock `firebase_admin` module used in `__init__.py`.
        self.mocks["init_firebase_admin"].auth = self.mock_auth_service

        # Create the Flask app *after* all patches are active.
        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()

    def _simulate_login(self, user_id, token_payload, firestore_data):
        """
        A generic helper to configure mocks for a logged-in user.
        """
        # Configure mocks for the `before_request` handler (token verification).
        self.mock_auth_service.verify_id_token.return_value = token_payload

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection.return_value

        # Configure the mock document that will be returned by the get() call.
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = firestore_data

        # Specifically mock the document call for the user_id being simulated.
        def document_side_effect(doc_id):
            if doc_id == user_id:
                mock_user_doc = MagicMock()
                mock_user_doc.get.return_value = mock_doc_snapshot
                return mock_user_doc
            return MagicMock()  # Return a generic mock for other calls

        mock_users_collection.document.side_effect = document_side_effect

        # Mock the admin check in the login route to prevent redirects to /install.
        mock_users_collection.where.return_value.limit.return_value.get.return_value = [
            MagicMock()
        ]

        return {"Authorization": "Bearer mock-token"}

    def test_admin_panel_access_by_admin(self):
        """Test that an admin user can access the admin panel."""
        headers = self._simulate_login(
            MOCK_ADMIN_ID, MOCK_ADMIN_PAYLOAD, MOCK_ADMIN_DATA
        )

        # The admin route also queries for the email verification setting. Mock this call.
        mock_settings_doc = self.mock_firestore_service.client.return_value.collection(
            "settings"
        ).document("enforceEmailVerification")
        mock_settings_doc.get.return_value.exists = False

        response = self.client.get("/admin/", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Panel", response.data)

    def test_admin_panel_access_denied_for_non_admin(self):
        """Test that a non-admin user is redirected from the admin panel."""
        headers = self._simulate_login(MOCK_USER_ID, MOCK_USER_PAYLOAD, MOCK_USER_DATA)

        response = self.client.get("/admin/", headers=headers, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You are not authorized", response.data)
        self.assertNotIn(b"Admin Panel", response.data)


if __name__ == "__main__":
    unittest.main()
