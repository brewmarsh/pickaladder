"""Tests for the Design System Style Guide."""

import unittest
from typing import Any
from unittest.mock import MagicMock, patch
from flask import g
from pickaladder import create_app

# Mock user payloads
MOCK_ADMIN_ID = "admin_uid"
MOCK_ADMIN_DATA = {"uid": "admin_uid", "name": "Admin User", "isAdmin": True}

class StyleGuideTestCase(unittest.TestCase):
    """Test case for the design system style guide."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch("firebase_admin.firestore.client"),
            "match_service_record": patch("pickaladder.match.services.MatchService.record_match"),
            "user_service_get_all": patch("pickaladder.user.UserService.get_all_users"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _login_admin(self) -> None:
        """Simulate an admin user login."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_ADMIN_ID
            sess["is_admin"] = True

        mock_db = self.mocks["firestore_client"].return_value
        mock_user_doc = MagicMock()
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_ADMIN_DATA
        mock_user_doc.get.return_value = mock_user_snapshot
        mock_db.collection("users").document.return_value = mock_user_doc

    def test_style_guide_renders(self) -> None:
        """Ensure the new style guide page renders correctly for admin."""
        self._login_admin()

        # Mock g.user which is often used in templates/decorators
        with self.app.test_request_context():
            from pickaladder.user.models import UserSession
            g.user = UserSession(MOCK_ADMIN_DATA)

            # We need to use the client within this context if possible,
            # but usually session is enough for the actual request.
            response = self.client.get("/admin/style-guide")

            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Design System Style Guide", response.data)
            self.assertIn(b"Colors", response.data)
            self.assertIn(b"Volt", response.data)
            self.assertIn(b"Tournament Card", response.data)
            self.assertIn(b"Match Row", response.data)
            self.assertIn(b"style-guide-wrapper", response.data)

if __name__ == "__main__":
    unittest.main()
