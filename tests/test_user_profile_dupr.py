"""Test DUPR rating display on user profile."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class UserProfileDuprTestCase(unittest.TestCase):
    """Test case for the DUPR rating display on the user profile."""

    def setUp(self) -> None:
        """Set up the test case with mocks and app context."""
        self.mock_firestore_service = MagicMock()
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "storage": patch("pickaladder.user.services.profile.storage"),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
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
        """Tear down the test case and pop app context."""
        self.app_context.pop()

    def test_profile_dupr_display(self) -> None:
        """Test that the DUPR rating is correctly displayed on the profile page."""
        # Setup logged-in user
        with self.client.session_transaction() as sess:
            sess["user_id"] = "viewer_id"
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = {"uid": "viewer_id"}

        # Mock Firestore client
        mock_db = self.mock_firestore_service.client.return_value

        # Mock target user profile
        target_user_id = "target_user"
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "username": "target_user",
            "name": "Target User",
            "dupr_rating": 4.5,
            "profilePictureUrl": "http://example.com/pic.jpg",
        }

        # Setup mock db to return this user
        mock_db.collection("users").document(
            target_user_id
        ).get.return_value = mock_user_doc

        # Mock friends query to avoid errors
        mock_user_ref = mock_db.collection("users").document(target_user_id)
        mock_user_ref.collection(
            "friends"
        ).where.return_value.limit.return_value.stream.return_value = []

        # Mock matches queries
        mock_db.collection("matches").where.return_value.stream.return_value = []
        mock_db.collection(
            "matches"
        ).where.return_value.where.return_value.stream.return_value = []

        # Make request
        response = self.client.get(f"/user/{target_user_id}")

        # Check response
        self.assertEqual(response.status_code, 200)

        # Verify DUPR rating is present in HTML
        self.assertIn(b"DUPR Rating", response.data)
        self.assertIn(b"4.5", response.data)
