"""Tests for the Brag Card feature."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}


class BragCardTestCase(unittest.TestCase):
    """Test case for the Brag Card feature."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
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
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

        # Mock the user document for before_request load_logged_in_user
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            "username": "testuser",
            "email": "test@example.com",
        }
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_user_doc
        )

    def _get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer mock-token"}

    def test_get_user_group_trend(self) -> None:
        """Test successfully fetching user-specific trend data."""
        self._set_session_user()

        group_id = "test_group"
        user_id = MOCK_USER_ID

        mock_trend_data = {
            "labels": ["2023-01-01", "2023-01-02"],
            "datasets": [
                {
                    "id": user_id,
                    "label": "Test User",
                    "data": [10.5, 12.0],
                    "profilePictureUrl": None,
                }
            ],
        }

        with patch(
            "pickaladder.group.routes.get_leaderboard_trend_data",
            return_value=mock_trend_data,
        ):
            response = self.client.get(
                f"/group/{group_id}/user-trend/{user_id}",
                headers=self._get_auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["labels"], ["2023-01-01", "2023-01-02"])
        self.assertEqual(data["dataset"]["id"], user_id)
        self.assertEqual(data["dataset"]["data"], [10.5, 12.0])

    def test_get_user_group_trend_not_found(self) -> None:
        """Test fetching trend data for a user not in the group."""
        self._set_session_user()

        group_id = "test_group"
        user_id = "other_user"

        mock_trend_data = {
            "labels": ["2023-01-01"],
            "datasets": [
                {
                    "id": "different_user",
                    "label": "Different User",
                    "data": [10.5],
                    "profilePictureUrl": None,
                }
            ],
        }

        with patch(
            "pickaladder.group.routes.get_leaderboard_trend_data",
            return_value=mock_trend_data,
        ):
            response = self.client.get(
                f"/group/{group_id}/user-trend/{user_id}",
                headers=self._get_auth_headers(),
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"], "User data not found for this group"
        )


if __name__ == "__main__":
    unittest.main()
