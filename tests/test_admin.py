"""Tests for the admin blueprint."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock user payloads
MOCK_ADMIN_ID = "admin_uid"
MOCK_ADMIN_PAYLOAD = {"uid": MOCK_ADMIN_ID, "email": "admin@example.com"}
MOCK_ADMIN_DATA = {"name": "Admin User", "isAdmin": True}

MOCK_USER_ID = "user_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user@example.com"}
MOCK_USER_DATA = {"name": "Regular User", "isAdmin": False}


class AdminRoutesTestCase(unittest.TestCase):
    """Test case for the admin blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.admin.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "user_firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
            ),
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

    def _login_user(
        self, user_id: str, user_data: dict[str, Any], is_admin: bool
    ) -> None:
        """Simulate a user login by setting the session and mocking Firestore."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["is_admin"] = is_admin

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")

        def document_side_effect(doc_id: str) -> MagicMock:
            """Firestore document side effect mock."""
            if doc_id == user_id:
                mock_user_doc = MagicMock()
                mock_user_snapshot = MagicMock()
                mock_user_snapshot.exists = True
                mock_user_snapshot.to_dict.return_value = user_data
                mock_user_doc.get.return_value = mock_user_snapshot
                return mock_user_doc
            return MagicMock()

        mock_users_collection.document.side_effect = document_side_effect

    def test_admin_panel_accessible_to_admin(self) -> None:
        """Ensure an admin user can access the admin panel."""
        self._login_user(MOCK_ADMIN_ID, MOCK_ADMIN_DATA, is_admin=True)

        # The admin route checks for the email verification setting, so we mock it.
        mock_settings_doc = self.mock_firestore_service.client.return_value.collection(
            "settings"
        ).document("enforceEmailVerification")
        mock_settings_doc.get.return_value.exists = False

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin Panel", response.data)

    def test_admin_panel_inaccessible_to_non_admin(self) -> None:
        """Ensure a non-admin user is redirected from the admin panel."""
        self._login_user(MOCK_USER_ID, MOCK_USER_DATA, is_admin=False)

        response = self.client.get("/admin/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You are not authorized to view this page.", response.data)
        self.assertNotIn(b"Admin Panel", response.data)

    @patch("pickaladder.admin.routes.UserService")
    def test_merge_ghost_user_success(self, mock_user_service: MagicMock) -> None:
        """Ensure an admin can merge a ghost user."""
        self._login_user(MOCK_ADMIN_ID, MOCK_ADMIN_DATA, is_admin=True)
        mock_user_service.merge_ghost_user.return_value = True

        response = self.client.post(
            "/admin/merge-ghost",
            data={"target_user_id": "real_user", "ghost_email": "ghost@example.com"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully merged ghost@example.com into real_user.", response.data)
        mock_user_service.merge_ghost_user.assert_called_once()

    @patch("pickaladder.admin.routes.UserService")
    def test_merge_ghost_user_failure(self, mock_user_service: MagicMock) -> None:
        """Ensure failure message is shown when merge fails."""
        self._login_user(MOCK_ADMIN_ID, MOCK_ADMIN_DATA, is_admin=True)
        mock_user_service.merge_ghost_user.return_value = False

        response = self.client.post(
            "/admin/merge-ghost",
            data={"target_user_id": "real_user", "ghost_email": "ghost@example.com"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Failed to merge ghost@example.com. Ghost account might not exist.", response.data)

    def test_merge_ghost_user_missing_fields(self) -> None:
        """Ensure error message is shown when fields are missing."""
        self._login_user(MOCK_ADMIN_ID, MOCK_ADMIN_DATA, is_admin=True)

        response = self.client.post(
            "/admin/merge-ghost",
            data={"target_user_id": "real_user"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Both Target User ID and Ghost Email are required.", response.data)


if __name__ == "__main__":
    unittest.main()
