"""Tests for the auth blueprint."""

from __future__ import annotations

import re
import unittest
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from re import Match

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app
from pickaladder.errors import DuplicateResourceError

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Test User", "isAdmin": False}
MOCK_PASSWORD = "Password123"  # nosec


class AuthFirebaseTestCase(unittest.TestCase):
    """Test case for the auth blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        # Mock EmailAlreadyExistsError to be a real exception class for catch blocks
        self.mock_auth_service.EmailAlreadyExistsError = type(
            "EmailAlreadyExistsError", (Exception,), {}
        )
        self.mock_firestore_service = MagicMock()
        self.mock_auth_service_provider = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "auth": patch("pickaladder.auth.routes.auth", new=self.mock_auth_service),
            "firestore": patch(
                "pickaladder.auth.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "auth_service": patch(
                "pickaladder.auth.routes.AuthService",
                new=self.mock_auth_service_provider,
            ),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app({"TESTING": True, "SERVER_NAME": "localhost"})
        self.client = self.app.test_client()

    def test_successful_registration(self) -> None:
        """Test user registration with valid data."""
        # Mock the AuthService.register_user call
        self.mock_auth_service_provider.register_user.return_value = {
            "uid": "new_user_uid",
            "merged": False,
            "pending_invites_count": 0,
        }

        # First, get the register page to get a valid CSRF token
        register_page_response = self.client.get("/auth/register")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": csrf_token,
                "username": "newuser",
                "email": "new@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful!", response.data)
        self.mock_auth_service_provider.register_user.assert_called_once()

    def test_login_page_loads(self) -> None:
        """Test that the login page loads correctly."""
        # Mock the admin check to prevent a redirect to /install.
        mock_db = self.mock_firestore_service.client.return_value
        mock_db.collection(
            "users"
        ).where.return_value.limit.return_value.get.return_value = [MagicMock()]

        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_session_login(self) -> None:
        """Test the session login endpoint."""
        # Mock the return value of verify_id_token
        self.mock_auth_service.verify_id_token.return_value = MOCK_USER_PAYLOAD

        # Mock the Firestore document
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_doc_snapshot

        # First, get the login page to get a valid CSRF token
        login_page_response = self.client.get("/auth/login")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            login_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/session_login",
            json={"idToken": "test_token"},
            headers={"X-CSRFToken": csrf_token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success"})
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], MOCK_USER_ID)
            self.assertEqual(sess["is_admin"], False)

    def test_install_admin_user(self) -> None:
        """Test the creation of the initial admin user."""
        # Mock the admin check to simulate no admin user exists.
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        (
            mock_users_collection.where.return_value.limit.return_value.get.return_value
        ) = []

        # Mock the return value of create_user
        self.mock_auth_service.create_user.return_value = MagicMock(
            uid="admin_user_uid"
        )

        # More specific mocking for document calls
        mock_user_doc = MagicMock()
        mock_settings_doc = MagicMock()

        def document_side_effect(doc_id: str) -> MagicMock:
            """Firestore document side effect mock."""
            if doc_id == "admin_user_uid":
                return mock_user_doc
            elif doc_id == "enforceEmailVerification":
                return mock_settings_doc
            return MagicMock()

        (
            self.mock_firestore_service.client.return_value.collection.return_value.document.side_effect
        ) = document_side_effect

        # First, get the install page to get a valid CSRF token
        install_page_response = self.client.get("/auth/install")
        csrf_token_match = re.search(
            r'name="csrf_token" value="([^"]+)"', install_page_response.data.decode()
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/install",
            data={
                "csrf_token": csrf_token,
                "username": "admin",
                "email": "admin@example.com",
                "password": MOCK_PASSWORD,
                "name": "Admin User",
                "dupr_rating": 5.0,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin user created successfully.", response.data)
        self.mock_auth_service.create_user.assert_called_once_with(
            email="admin@example.com",
            password=MOCK_PASSWORD,
            email_verified=True,
        )
        mock_user_doc.set.assert_called_once()
        mock_settings_doc.set.assert_called_once_with({"value": True})

    def test_registration_with_invite_token(self) -> None:
        """Test user registration with a valid invite token."""
        # Mock the AuthService.register_user call
        self.mock_auth_service_provider.register_user.return_value = {
            "uid": "new_user_uid",
            "merged": False,
            "pending_invites_count": 0,
        }

        # First, get the register page to get a valid CSRF token and set the
        # invite token in the session
        with self.client.session_transaction() as sess:
            sess["invite_token"] = "test_invite_token"  # nosec
        register_page_response = self.client.get(
            "/auth/register?invite_token=test_invite_token"
        )
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": csrf_token,
                "username": "newuser",
                "email": "new@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful!", response.data)

        # Check that the service was called with the invite token
        self.mock_auth_service_provider.register_user.assert_called_once()
        args, kwargs = self.mock_auth_service_provider.register_user.call_args
        self.assertEqual(kwargs.get("invite_token"), "test_invite_token")

    def test_registration_username_taken(self) -> None:
        """Test registration when username is already taken."""
        self.mock_auth_service_provider.register_user.side_effect = (
            DuplicateResourceError("Username already exists.")
        )

        # First, get the register page to get a valid CSRF token
        register_page_response = self.client.get("/auth/register")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": csrf_token,
                "username": "taken",
                "email": "new@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Username already exists.", response.data)

    def test_google_signin_new_user(self) -> None:
        """Test that a new user signing in with Google has their account created."""
        # Mock the return value of verify_id_token
        self.mock_auth_service.verify_id_token.return_value = MOCK_USER_PAYLOAD

        # Mock the Firestore document to simulate a new user
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        mock_user_doc.get.return_value = mock_doc_snapshot

        # Mock get_user to return a user record
        mock_user_record = MagicMock()
        mock_user_record.email = "new@example.com"
        mock_user_record.display_name = "New User"
        self.mock_auth_service.get_user.return_value = mock_user_record

        # Mock the where calls for both the admin check and the username check
        mock_admin_check = MagicMock()
        mock_admin_check.limit.return_value.get.return_value = [MagicMock()]
        mock_username_check = MagicMock()
        mock_username_check.limit.return_value.get.return_value = []
        mock_users_collection.where.side_effect = [
            mock_admin_check,
            mock_username_check,
        ]

        # First, get the login page to get a valid CSRF token
        login_page_response = self.client.get("/auth/login")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            login_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        response = self.client.post(
            "/auth/session_login",
            json={"idToken": "test_token"},
            headers={"X-CSRFToken": csrf_token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success"})
        mock_user_doc.set.assert_called_once()


if __name__ == "__main__":
    unittest.main()
