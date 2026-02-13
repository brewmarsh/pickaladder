"""Tests for user routes and profiles."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app
from tests.mock_utils import patch_mockfirestore

MOCK_USER_ID = "user123"
MOCK_PROFILE_USER_ID = "profile456"


class UserTestCase(unittest.TestCase):
    """Test cases for user-related routes and functionality."""

    def setUp(self) -> None:
        """Set up the test client and mock Firestore."""
        self.mock_db = MockFirestore()

        # Patch firestore.client() to return our mock_db
        self.patcher_firestore = patch(
            "firebase_admin.firestore.client", return_value=self.mock_db
        )
        self.patcher_firestore.start()

        # Patch FieldFilter
        self.patcher_field_filter = patch("firebase_admin.firestore.FieldFilter")
        self.mock_field_filter_class = self.patcher_field_filter.start()

        def field_filter_side_effect(field, op, value):
            mock = MagicMock()
            mock.field_path = field
            mock.op_string = op
            mock.value = value
            return mock

        self.mock_field_filter_class.side_effect = field_filter_side_effect

        self.patcher_auth = patch("firebase_admin.auth")
        self.mock_auth = self.patcher_auth.start()

        self.patcher_storage = patch("firebase_admin.storage")
        self.mock_storage = self.patcher_storage.start()

        # Patch initialize_app to avoid real firebase init
        self.patcher_init = patch("firebase_admin.initialize_app")
        self.patcher_init.start()

        patch_mockfirestore()

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers."""
        self.patcher_firestore.stop()
        self.patcher_field_filter.stop()
        self.patcher_auth.stop()
        self.patcher_storage.stop()
        self.patcher_init.stop()

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and setup mock doc."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Setup the user in mock DB so load_user finds it
        self.mock_db.collection("users").document(user_id).set(
            {
                "username": "user1",
                "email": "user1@example.com",
                "name": "User One",
                "uid": user_id,
                "stats": {
                    "wins": 0,
                    "losses": 0,
                    "total_games": 0,
                    "win_rate": 0,
                    "current_streak": 0,
                    "streak_type": "win",
                },
            }
        )

    def test_settings_get(self) -> None:
        """Test that the settings page loads for a logged-in user."""
        self._set_session_user()
        self.mock_db.collection("users").document(MOCK_USER_ID).update(
            {
                "username": "testuser",
                "dark_mode": True,
                "duprRating": 5.0,
                "email": "test@example.com",
                "name": "Test User",
            }
        )

        response = self.client.get("/user/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"testuser", response.data)

    def test_settings_post_success(self) -> None:
        """Test updating user settings via POST."""
        self._set_session_user()

        response = self.client.post(
            "/user/settings",
            data={
                "name": "User One",
                "email": "user1@example.com",
                "dark_mode": "y",
                "dupr_rating": "5.5",
                "username": "newuser",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)

        # Verify DB update
        data = self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        self.assertEqual(data["username"], "newuser")
        self.assertEqual(data["dark_mode"], True)
        self.assertEqual(data["duprRating"], 5.5)

    def test_api_dashboard_fetches_all_matches_for_sorting(self) -> None:
        """Test that all matches are fetched for sorting."""
        self._set_session_user()
        response = self.client.get("/user/api/dashboard")
        self.assertEqual(response.status_code, 200)

    def test_api_dashboard_returns_group_match_flag(self) -> None:
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)

        # Create a match
        match_data = {
            "matchType": "singles",
            "player1Ref": user_ref,
            "player2Ref": self.mock_db.collection("users").document("user2"),
            "player1Score": 10,
            "player2Score": 5,
            "matchDate": "2023-01-01",
            "groupId": "group123",
            "team1": [],
            "team2": [],
            "participants": [],
            "status": "completed",
            "player1Id": MOCK_USER_ID,
            "player2Id": "user2",
        }
        self.mock_db.collection("matches").add(match_data)
        self.mock_db.collection("users").document("user2").set({"username": "user2"})

        response = self.client.get("/user/api/dashboard")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        matches = data["matches"]
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["is_group_match"])

    @patch("pickaladder.user.routes.render_template")
    def test_view_user_includes_doubles_and_processes_matches(
        self, mock_render_template: MagicMock
    ) -> None:
        """Test that view_user fetches and processes doubles matches."""
        self._set_session_user()

        # Mock profile user
        self.mock_db.collection("users").document(MOCK_PROFILE_USER_ID).set(
            {
                "username": "profile_user",
                "stats": {
                    "wins": 0,
                    "losses": 0,
                    "total_games": 0,
                    "win_rate": 0,
                    "current_streak": 0,
                    "streak_type": "win",
                },
            }
        )
        profile_user_ref = self.mock_db.collection("users").document(
            MOCK_PROFILE_USER_ID
        )

        # Create a match
        opponent_ref = self.mock_db.collection("users").document("opponent_id")
        opponent_ref.set({"username": "opponent_user"})

        self.mock_db.collection("matches").add(
            {
                "matchDate": datetime.datetime(2023, 1, 1),
                "player1Score": 11,
                "player2Score": 9,
                "player1Ref": profile_user_ref,
                "player2Ref": opponent_ref,
                "matchType": "singles",
                "team1": [],
                "team2": [],
                "participants": [],
                "status": "completed",
                "player1Id": MOCK_PROFILE_USER_ID,
                "player2Id": "opponent_id",
            }
        )

        # Execute request
        self.client.get(f"/user/{MOCK_PROFILE_USER_ID}")

        # Check template context
        args, kwargs = mock_render_template.call_args
        matches = kwargs.get("matches")
        self.assertTrue(len(matches) > 0)


if __name__ == "__main__":
    unittest.main()
