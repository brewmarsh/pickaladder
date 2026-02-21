from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from pickaladder.auth.services import AuthService
from pickaladder.errors import DuplicateResourceError
from firebase_admin import auth

class TestAuthService(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()
        self.email = "test@example.com"
        self.password = "Password123"
        self.username = "testuser"
        self.name = "Test User"
        self.dupr_rating = 4.5

    @patch("pickaladder.auth.services.auth")
    @patch("pickaladder.auth.services.send_email")
    @patch("pickaladder.auth.services.UserService")
    def test_register_user_success(self, mock_user_service: MagicMock, mock_send_email: MagicMock, mock_auth: MagicMock) -> None:
        """Test successful user registration."""
        # Setup mocks
        self.db.collection.return_value.where.return_value.limit.return_value.get.return_value = [] # Username available
        mock_auth.create_user.return_value = MagicMock(uid="new_uid")
        mock_auth.generate_email_verification_link.return_value = "http://link"
        mock_user_service.merge_ghost_user.return_value = False

        result = AuthService.register_user(
            self.db, self.email, self.password, self.username, self.name, self.dupr_rating
        )

        self.assertEqual(result["uid"], "new_uid")
        self.assertFalse(result["merged"])
        self.assertEqual(result["pending_invites_count"], 0)

        mock_auth.create_user.assert_called_once_with(
            email=self.email, password=self.password, email_verified=False
        )
        # Check Firestore document creation
        self.db.collection.assert_any_call("users")
        self.db.collection("users").document("new_uid").set.assert_called_once()
        mock_send_email.assert_called_once()

    def test_register_user_username_taken(self) -> None:
        """Test registration when username is already taken."""
        self.db.collection.return_value.where.return_value.limit.return_value.get.return_value = [MagicMock()] # Username taken

        with self.assertRaises(DuplicateResourceError):
            AuthService.register_user(
                self.db, self.email, self.password, self.username, self.name, self.dupr_rating
            )

    @patch("pickaladder.auth.services.auth")
    def test_register_user_email_taken(self, mock_auth: MagicMock) -> None:
        """Test registration when email is already taken."""
        # Define a mock exception class because Firebase exceptions are complex to instantiate
        EmailAlreadyExistsError = type("EmailAlreadyExistsError", (Exception,), {})
        mock_auth.EmailAlreadyExistsError = EmailAlreadyExistsError

        self.db.collection.return_value.where.return_value.limit.return_value.get.return_value = [] # Username available
        mock_auth.create_user.side_effect = EmailAlreadyExistsError("error")

        with self.assertRaises(EmailAlreadyExistsError):
            AuthService.register_user(
                self.db, self.email, self.password, self.username, self.name, self.dupr_rating
            )

    @patch("pickaladder.auth.services.auth")
    @patch("pickaladder.auth.services.send_email")
    @patch("pickaladder.auth.services.UserService")
    def test_register_user_with_referrer(self, mock_user_service: MagicMock, mock_send_email: MagicMock, mock_auth: MagicMock) -> None:
        """Test registration with a referrer."""
        self.db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
        mock_auth.create_user.return_value = MagicMock(uid="new_uid")

        AuthService.register_user(
            self.db, self.email, self.password, self.username, self.name, self.dupr_rating,
            referrer_id="referrer_uid"
        )

        # Check that referred_by was set
        args, kwargs = self.db.collection("users").document("new_uid").set.call_args
        self.assertEqual(args[0]["referred_by"], "referrer_uid")

        # Check that referral count was incremented
        self.db.collection("users").document("referrer_uid").update.assert_called_once()

    @patch("pickaladder.auth.services.auth")
    @patch("pickaladder.auth.services.send_email")
    @patch("pickaladder.auth.services.UserService")
    def test_register_user_with_invite_token(self, mock_user_service: MagicMock, mock_send_email: MagicMock, mock_auth: MagicMock) -> None:
        """Test registration with an invite token."""
        self.db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
        mock_auth.create_user.return_value = MagicMock(uid="new_uid")

        # Mock invite document
        mock_invite = MagicMock()
        mock_invite.exists = True
        mock_invite.to_dict.return_value = {"userId": "inviter_uid", "used": False}
        self.db.collection("invites").document.return_value.get.return_value = mock_invite

        AuthService.register_user(
            self.db, self.email, self.password, self.username, self.name, self.dupr_rating,
            invite_token="token123"
        )

        # Check that friendship was created via batch
        self.db.batch.return_value.commit.assert_called_once()
        self.db.collection("invites").document("token123").update.assert_called_once_with({"used": True})

if __name__ == "__main__":
    unittest.main()
