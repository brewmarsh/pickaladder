"""Tests for the welcome toast functionality."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock data
MOCK_USER_ID = "real_uid"
MOCK_GHOST_ID = "ghost_uid"
MOCK_EMAIL = "ghost@example.com"


class WelcomeToastTestCase(unittest.TestCase):
    """Test case for the welcome toast functionality."""

    def setUp(self) -> None:
        """Set up a test client and mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        # Patchers for all dependencies
        self.patchers = [
            patch("firebase_admin.initialize_app"),
            patch("pickaladder.auth.routes.auth", new=self.mock_auth_service),
            patch("pickaladder.auth.routes.firestore", new=self.mock_firestore_service),
            patch("pickaladder.auth.routes.UserService.merge_ghost_user"),
        ]

        self.mocks = []
        for p in self.patchers:
            self.mocks.append(p.start())

        self.mock_merge_ghost_user = self.mocks[-1]

        # Mock the username check to return an empty list
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        (
            mock_users_collection.where.return_value.limit.return_value.get.return_value
        ) = []

        self.app = create_app(
            {"TESTING": True, "SERVER_NAME": "localhost", "WTF_CSRF_ENABLED": False}
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers."""
        for p in self.patchers:
            p.stop()

    @patch("pickaladder.auth.routes.UserService.get_pending_tournament_invites")
    def test_welcome_toast_triggered_on_merge(
        self, mock_get_invites: MagicMock
    ) -> None:
        """Test welcome toast session flag is set when a ghost user is merged."""
        # 1. Mock verify_id_token to return a user payload
        self.mock_auth_service.verify_id_token.return_value = {"uid": MOCK_USER_ID}

        # 2. Mock Firestore to simulate a new user registration via session login
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.get.return_value.exists = False  # New user

        # Mock user record from auth
        mock_user_record = MagicMock()
        mock_user_record.email = MOCK_EMAIL
        mock_user_record.display_name = "Real User"
        self.mock_auth_service.get_user.return_value = mock_user_record

        # 3. Mock merge_ghost_user to return True (merge occurred)
        self.mock_merge_ghost_user.return_value = True

        # 4. Mock pending invites count
        mock_get_invites.return_value = [{"id": "t1"}, {"id": "t2"}]

        # 5. Call session_login
        response = self.client.post(
            "/auth/session_login",
            json={"idToken": "valid_token"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)

        # 6. Verify session flag
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("show_welcome_invites"), 2)

    @patch("pickaladder.auth.routes.UserService.get_pending_tournament_invites")
    def test_welcome_toast_not_triggered_on_no_merge(
        self, mock_get_invites: MagicMock
    ) -> None:
        """Test welcome toast flag is NOT set when no merge occurred."""
        self.mock_auth_service.verify_id_token.return_value = {"uid": MOCK_USER_ID}
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.get.return_value.exists = False  # New user

        mock_user_record = MagicMock()
        mock_user_record.email = MOCK_EMAIL
        mock_user_record.display_name = "Real User"
        self.mock_auth_service.get_user.return_value = mock_user_record

        # merge_ghost_user returns False
        self.mock_merge_ghost_user.return_value = False

        response = self.client.post(
            "/auth/session_login",
            json={"idToken": "valid_token"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("show_welcome_invites"))

        mock_get_invites.assert_not_called()

    @patch("pickaladder.auth.routes.send_email")
    @patch("pickaladder.auth.routes.UserService.get_pending_tournament_invites")
    def test_welcome_toast_triggered_on_register(
        self, mock_get_invites: MagicMock, mock_send_email: MagicMock
    ) -> None:
        """Test welcome toast flag is set when a user registers and is merged."""
        # Mock auth create_user
        self.mock_auth_service.create_user.return_value = MagicMock(uid=MOCK_USER_ID)
        self.mock_auth_service.generate_email_verification_link.return_value = (
            "http://link"
        )

        # 3. Mock merge_ghost_user to return True
        self.mock_merge_ghost_user.return_value = True

        # 4. Mock pending invites count
        mock_get_invites.return_value = [{"id": "t1"}]

        # 5. Call register
        response = self.client.post(
            "/auth/register",
            data={
                "username": "newuser",
                "email": MOCK_EMAIL,
                "password": "Password123",  # nosec
                "confirm_password": "Password123",  # nosec
                "name": "New User",
                "dupr_rating": "4.5",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

        # 6. Verify session flag
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("show_welcome_invites"), 1)


if __name__ == "__main__":
    unittest.main()
