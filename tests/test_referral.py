"""Tests for the referral system."""

from __future__ import annotations

import re
import unittest
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from re import Match

from pickaladder import create_app

# Mock user payloads
REFERRER_ID = "referrer_uid"
MOCK_PASSWORD = "Password123"  # nosec


class ReferralTestCase(unittest.TestCase):
    """Test case for the referral system."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "auth": patch("pickaladder.auth.routes.auth", new=self.mock_auth_service),
            "firestore_auth": patch(
                "pickaladder.auth.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_group": patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
            ),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app({"TESTING": True, "SERVER_NAME": "localhost"})
        self.client = self.app.test_client()

    def test_capture_referrer_in_session(self) -> None:
        """Test that the view_group route captures the referrer ID in the session."""
        # Mock Firestore user doc for before_request
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document("test_user_id")
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {"uid": "test_user_id", "username": "testuser"}
        mock_user_doc.get.return_value = mock_snapshot

        # Mock login
        with self.client.session_transaction() as sess:
            sess["user_id"] = "test_user_id"

        # Mock group details to avoid error
        with patch("pickaladder.group.routes.GroupService.get_group_details") as mock_get:
            mock_get.return_value = {
                "group": {"id": "group1", "name": "Group 1"},
                "eligible_friends": [],
                "leaderboard": [],
                "recent_matches": [],
                "best_buds": None,
                "team_leaderboard": [],
                "is_member": True,
                "members": [],
                "pending_members": [],
            }
            response = self.client.get(f"/group/group1?ref={REFERRER_ID}")
            self.assertEqual(response.status_code, 200)

            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("referrer_id"), REFERRER_ID)

    @patch("pickaladder.auth.routes.send_email")
    def test_attribution_on_registration(self, mock_send_email: MagicMock) -> None:
        """Test that referral is attributed during registration."""
        # Set referrer in session
        with self.client.session_transaction() as sess:
            sess["referrer_id"] = REFERRER_ID

        mock_db = self.mock_firestore_service.client.return_value

        # Mock username availability check
        mock_users_collection = mock_db.collection("users")
        mock_users_collection.where.return_value.limit.return_value.get.return_value = []

        # Mock user creation in Auth
        self.mock_auth_service.create_user.return_value = MagicMock(uid="new_user_uid")

        # Get CSRF token
        register_page_response = self.client.get("/auth/register")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        csrf_token = cast("Match[str]", csrf_token_match).group(1)

        # Post registration
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

        # Verify new user document has referred_by
        mock_new_user_doc = mock_db.collection("users").document("new_user_uid")
        mock_new_user_doc.set.assert_called_once()
        args, _ = mock_new_user_doc.set.call_args
        self.assertEqual(args[0]["referred_by"], REFERRER_ID)

        # Verify referrer count was incremented
        mock_referrer_doc = mock_db.collection("users").document(REFERRER_ID)
        mock_referrer_doc.update.assert_called_once()
        args, _ = mock_referrer_doc.update.call_args
        self.assertIn("referral_count", args[0])

        # Verify session was cleared
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("referrer_id"))

if __name__ == "__main__":
    unittest.main()
