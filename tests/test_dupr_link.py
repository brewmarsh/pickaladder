"""Test DUPR profile linking."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.core.constants import DUPR_PROFILE_BASE_URL


class DuprLinkTestCase(unittest.TestCase):
    """Test case for DUPR profile linking functionality."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.mock_firestore_client = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch("google.cloud.firestore_v1.client.Client"),
            "firestore_admin_client": patch(
                "firebase_admin.firestore.client",
                return_value=self.mock_firestore_client,
            ),
            "auth": patch("firebase_admin.auth"),
            "storage": patch("firebase_admin.storage"),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
            "send_email": patch("pickaladder.user.routes.send_email"),
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
        """Tear down the test case."""
        self.app_context.pop()

    def test_edit_profile_dupr_update(self) -> None:
        """Test that dupr_id and dupr_rating are updated in the edit_profile route."""
        user_id = "test_user"
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["is_admin"] = False

        # Mock user document for before_request
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "uid": user_id,
            "username": "testuser",
            "email": "test@example.com",
            "name": "Test User",
        }
        (
            self.mock_firestore_client.collection.return_value.document.return_value.get.return_value
        ) = mock_user_doc

        # Post data to edit_profile
        with patch(
            "pickaladder.user.routes.UserService.update_user_profile"
        ) as mock_update:
            response = self.client.post(
                "/user/edit_profile",
                data={
                    "name": "Updated User",
                    "username": "testuser",
                    "email": "test@example.com",
                    "dupr_id": " 12345 ",
                    "dupr_rating": "4.25",
                },
                follow_redirects=True,
            )

            self.assertEqual(response.status_code, 200)
            mock_update.assert_called_once()
            args = mock_update.call_args[0]
            self.assertEqual(args[1], user_id)
            self.assertEqual(args[2]["dupr_id"], "12345")
            self.assertEqual(args[2]["dupr_rating"], 4.25)

    def test_profile_dupr_link_display(self) -> None:
        """Test that the DUPR link is displayed on the profile page."""
        user_id = "viewer_id"
        target_id = "target_id"
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["is_admin"] = False

        # Mock viewer user
        mock_viewer_doc = MagicMock()
        mock_viewer_doc.exists = True
        mock_viewer_doc.to_dict.return_value = {"uid": user_id, "username": "viewer"}

        # Mock target user
        mock_target_doc = MagicMock()
        mock_target_doc.exists = True
        mock_target_doc.to_dict.return_value = {
            "uid": target_id,
            "username": "targetuser",
            "name": "Target User",
            "dupr_id": "67890",
            "dupr_rating": 5.0,
        }

        def get_doc(doc_id: str) -> Any:
            if doc_id == user_id:
                return mock_viewer_doc
            if doc_id == target_id:
                return mock_target_doc
            return MagicMock(exists=False)

        self.mock_firestore_client.collection.return_value.document.side_effect = (
            lambda doc_id: MagicMock(get=lambda: get_doc(doc_id))
        )

        # Mock other dependencies
        (
            self.mock_firestore_client.collection.return_value.document.return_value.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = []
        (
            self.mock_firestore_client.collection.return_value.where.return_value.stream.return_value
        ) = []

        response = self.client.get(f"/user/{target_id}")
        self.assertEqual(response.status_code, 200)

        self.assertIn(b"DUPR", response.data)
        expected_url = (DUPR_PROFILE_BASE_URL + "67890").encode()
        self.assertIn(expected_url, response.data)
        self.assertIn(b'target="_blank"', response.data)

    def test_profile_no_dupr_link_display(self) -> None:
        """Test that 'Add DUPR ID' is displayed when DUPR ID is missing."""
        user_id = "viewer_id"
        target_id = "target_id"
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["is_admin"] = False

        # Mock viewer user
        mock_viewer_doc = MagicMock()
        mock_viewer_doc.exists = True
        mock_viewer_doc.to_dict.return_value = {"uid": user_id, "username": "viewer"}

        # Mock target user without dupr_id
        mock_target_doc = MagicMock()
        mock_target_doc.exists = True
        mock_target_doc.to_dict.return_value = {
            "uid": target_id,
            "username": "targetuser",
            "name": "Target User",
            "dupr_rating": 3.5,
        }

        def get_doc(doc_id: str) -> Any:
            if doc_id == user_id:
                return mock_viewer_doc
            if doc_id == target_id:
                return mock_target_doc
            return MagicMock(exists=False)

        self.mock_firestore_client.collection.return_value.document.side_effect = (
            lambda doc_id: MagicMock(get=lambda: get_doc(doc_id))
        )

        # Mock other dependencies
        (
            self.mock_firestore_client.collection.return_value.document.return_value.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = []
        (
            self.mock_firestore_client.collection.return_value.where.return_value.stream.return_value
        ) = []

        response = self.client.get(f"/user/{target_id}")
        self.assertEqual(response.status_code, 200)

        self.assertIn(b"Add DUPR ID", response.data)
        self.assertIn(b"3.5", response.data)
