"""Test DUPR rating display on user profile."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class UserProfileDuprTestCase(unittest.TestCase):
    """Test case for the DUPR rating display on the user profile."""

    def setUp(self) -> None:
        """Set up the test case with mocks and app context."""
        self.mock_db = MagicMock()
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch(
                "firebase_admin.firestore.client", return_value=self.mock_db
            ),
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

    def _setup_profile_mocks(
        self, viewer_id: str, target_user_id: str, target_user_data: dict[str, Any]
    ) -> None:
        """Helper to setup all necessary Firestore mocks for the profile view."""
        # Mock viewer profile
        mock_viewer_doc = MagicMock()
        mock_viewer_doc.exists = True
        mock_viewer_doc.to_dict.return_value = {
            "username": "viewer",
            "name": "Viewer User",
            "uid": viewer_id,
        }
        mock_viewer_doc.get.return_value = mock_viewer_doc

        # Mock target user profile
        mock_target_user_doc = MagicMock()
        mock_target_user_doc.exists = True
        mock_target_user_doc.id = target_user_id
        mock_target_user_doc.to_dict.return_value = target_user_data
        mock_target_user_doc.get.return_value = mock_target_user_doc

        def document_side_effect(doc_id):
            if doc_id == viewer_id:
                return mock_viewer_doc
            if doc_id == target_user_id:
                return mock_target_user_doc
            return MagicMock()

        self.mock_db.collection.return_value.document.side_effect = document_side_effect

        # Mock friends query
        self.mock_db.collection.return_value.document.return_value.collection.return_value.where.return_value.limit.return_value.stream.return_value = []

        # Mock matches queries
        self.mock_db.collection("matches").where.return_value.stream.return_value = []
        self.mock_db.collection(
            "matches"
        ).where.return_value.where.return_value.stream.return_value = []

    def test_profile_dupr_display(self) -> None:
        """Test that the DUPR rating and badge are correctly displayed on the profile page."""
        # Setup logged-in user
        viewer_id = "viewer_id"
        with self.client.session_transaction() as sess:
            sess["user_id"] = viewer_id
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = {"uid": viewer_id}

        target_user_id = "target_user"
        target_user_data = {
            "username": "target_user",
            "name": "Target User",
            "dupr_rating": 4.5,
            "dupr_id": "123456",
            "profilePictureUrl": "http://example.com/pic.jpg",
        }

        self._setup_profile_mocks(viewer_id, target_user_id, target_user_data)

        # Make request
        response = self.client.get(f"/user/{target_user_id}")

        # Check response
        self.assertEqual(response.status_code, 200)

        # Verify new UI label "Rating" is present instead of "DUPR Rating"
        self.assertIn(b"Rating", response.data)
        # Verify mock DUPR rating value "4.5" is present
        self.assertIn(b"4.5", response.data)
        # Verify DUPR badge "View on DUPR" is present because dupr_id exists
        self.assertIn(b"View on DUPR", response.data)

    def test_profile_no_dupr_id_no_badge(self) -> None:
        """Test that the DUPR badge is NOT displayed when dupr_id is missing."""
        # Setup logged-in user
        viewer_id = "viewer_id"
        with self.client.session_transaction() as sess:
            sess["user_id"] = viewer_id
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = {"uid": viewer_id}

        target_user_id = "target_user"
        target_user_data = {
            "username": "target_user",
            "dupr_rating": 3.5,
            "dupr_id": None,
        }

        self._setup_profile_mocks(viewer_id, target_user_id, target_user_data)

        # Make request
        response = self.client.get(f"/user/{target_user_id}")

        # Verify "View on DUPR" badge is NOT present
        self.assertNotIn(b"View on DUPR", response.data)
        self.assertIn(b"Rating", response.data)
        self.assertIn(b"3.5", response.data)
