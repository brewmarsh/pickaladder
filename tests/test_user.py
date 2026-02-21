"""Tests for the user blueprint using mockfirestore."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {
    "name": "Test User",
    "email": "user1@example.com",
    "isAdmin": False,
    "username": "user1",
    "profilePictureUrl": "default",
}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the user blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_db = MockFirestore()

        # Patch firestore.client() to return our mock_db
        self.mock_firestore_module = MagicMock()
        self.mock_firestore_module.client.return_value = self.mock_db

        # Mock FieldFilter and other constants
        class MockFieldFilter:
            def __init__(self, field_path: str, op_string: str, value: Any) -> None:
                self.field_path = field_path
                self.op_string = op_string
                self.value = value

        self.mock_firestore_module.FieldFilter = MockFieldFilter
        self.mock_firestore_module.SERVER_TIMESTAMP = "2023-01-01"

        # Mock storage and auth
        self.mock_storage = MagicMock()
        self.mock_auth = MagicMock()

        # Define a mock exception for auth.EmailAlreadyExistsError
        class EmailAlreadyExistsError(Exception):
            pass

        self.mock_auth.EmailAlreadyExistsError = EmailAlreadyExistsError

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch("firebase_admin.firestore.client"),
            "storage_bucket": patch("firebase_admin.storage.bucket"),
            "auth_module": patch("firebase_admin.auth"),
            "firestore_module": patch(
                "pickaladder.firestore", new=self.mock_firestore_module
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
            # Also patch specifically where it's used in services to avoid 'default app' issues
            "service_storage": patch("pickaladder.user.services.profile.storage"),
            "service_auth": patch(
                "pickaladder.user.services.core.auth", new=self.mock_auth
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

        # Setup current user in mock DB
        self.mock_db.collection("users").document(MOCK_USER_ID).set(
            MOCK_USER_DATA.copy()
        )

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self, is_admin: bool = False) -> None:
        """Set a logged-in user in the session and mock DB."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = is_admin
        self.mock_db.collection("users").document(MOCK_USER_ID).update(
            {"isAdmin": is_admin}
        )
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self) -> dict[str, str]:
        """Get standard authentication headers for tests."""
        return {"Authorization": "Bearer mock-token"}

    def test_settings_page_loads(self) -> None:
        """Test that the settings page loads for a logged-in user."""
        self._set_session_user()

        response = self.client.get("/user/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account Settings", response.data)

    def test_update_settings_success(self) -> None:
        """Test successfully updating user settings."""
        self._set_session_user()

        response = self.client.post(
            "/user/settings",
            data={
                "name": "Updated Name",
                "email": "updated@example.com",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)

        # Verify update in DB
        user_doc = self.mock_db.collection("users").document(MOCK_USER_ID).get()
        self.assertEqual(user_doc.to_dict()["name"], "Updated Name")
        self.assertEqual(user_doc.to_dict()["email"], "updated@example.com")

    def test_update_settings_email_exists(self) -> None:
        """Test updating settings with an already registered email."""
        self._set_session_user()

        # Mock auth to raise EmailAlreadyExistsError
        self.mock_auth.update_user.side_effect = (
            self.mock_auth.EmailAlreadyExistsError()
        )

        response = self.client.post(
            "/user/settings",
            data={
                "name": "Test User",
                "email": "exists@example.com",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This email is already in use", response.data)

    def test_profile_page_loads(self) -> None:
        """Test viewing own profile."""
        self._set_session_user()

        response = self.client.get(f"/user/{MOCK_USER_ID}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test User", response.data)

    def test_community_page_search(self) -> None:
        """Test searching on the community page."""
        self._set_session_user()

        # Seed another user
        self.mock_db.collection("users").document("other").set(
            {"name": "Other Player", "username": "other_p"}
        )

        response = self.client.get("/user/community?search=Other")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Other Player", response.data)


if __name__ == "__main__":
    unittest.main()
