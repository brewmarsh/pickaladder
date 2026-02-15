import datetime
import unittest
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app
from tests.mock_utils import patch_mockfirestore

# Mock user payloads for consistent test data
MOCK_USER_ID = "user1"
MOCK_PROFILE_USER_ID = "user2"
MOCK_FIREBASE_TOKEN_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_FIRESTORE_USER_DATA = {
    "name": "User One",
    "email": "user1@example.com",
    "username": "user1",
    "isAdmin": True,
    "uid": "user1",
    "stats": {
        "wins": 10,
        "losses": 5,
        "total_games": 15,
        "win_rate": 66.7,
        "current_streak": 2,
        "streak_type": "win",
    },
}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for user routes with Firebase mocks."""

    def setUp(self) -> None:
        """Set up the test case with full mock isolation."""
        self.mock_db = MockFirestore()
        self.mock_auth_service = MagicMock()
        self.mock_auth_service.EmailAlreadyExistsError = type(
            "EmailAlreadyExistsError", (Exception,), {}
        )
        self.mock_storage_service = MagicMock()

        self.patches = [
            patch("firebase_admin.initialize_app"),
            patch("firebase_admin.firestore.client", return_value=self.mock_db),
            patch("pickaladder.user.services.core.auth", new=self.mock_auth_service),
            patch("pickaladder.user.services.profile.auth", new=self.mock_auth_service),
            patch(
                "pickaladder.user.services.core.storage", new=self.mock_storage_service
            ),
            patch(
                "pickaladder.user.services.profile.storage",
                new=self.mock_storage_service,
            ),
            patch(
                "firebase_admin.auth.verify_id_token",
                return_value=MOCK_FIREBASE_TOKEN_PAYLOAD,
            ),
            patch("firebase_admin.auth"),
            patch("firebase_admin.storage"),
            patch("pickaladder.user.services.core.send_email"),
        ]

        for p in self.patches:
            p.start()

        patch_mockfirestore()

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers."""
        for p in self.patches:
            p.stop()

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and setup mock doc."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Populate the mock DB so the application's user-loader can find the user
        self.mock_db.collection("users").document(user_id).set(MOCK_FIRESTORE_USER_DATA)

    def _mock_firestore_user(
        self, user_id: str = MOCK_USER_ID, data: dict[str, Any] | None = None
    ) -> Any:
        """Setup a mock user document in Firestore and return the reference."""
        if data is None:
            data = MOCK_FIRESTORE_USER_DATA
        doc_ref = self.mock_db.collection("users").document(user_id)
        doc_ref.set(data)
        return doc_ref

    def test_settings_get(self) -> None:
        """Test that the settings page loads for a logged-in user."""
        self._set_session_user()
        self._mock_firestore_user()

        response = self.client.get("/user/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"user1", response.data)

    def test_settings_post_success(self) -> None:
        """Test updating user settings via POST."""
        self._set_session_user()

        response = self.client.post(
            "/user/settings",
            data={
                "name": "New Name",
                "email": "user1@example.com",
                "dark_mode": "y",
                "dupr_rating": 5.5,
                "username": "newuser",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)

        updated_data = (
            self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        )
        self.assertEqual(updated_data["name"], "New Name")

    def test_update_profile_picture_upload(self) -> None:
        """Test uploading a profile picture."""
        self._set_session_user()

        mock_bucket = self.mock_storage_service.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "profile_picture": (BytesIO(b"test_image_data"), "test.png"),
            "username": "user1",
            "name": "User One",
            "email": "user1@example.com",
        }
        response = self.client.post(
            "/user/settings",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)
        self.mock_storage_service.bucket.assert_called()
        mock_bucket.blob.assert_called_with(f"profile_pictures/{MOCK_USER_ID}/test.png")

    def test_update_dupr_and_dark_mode(self) -> None:
        """Test updating DUPR rating and dark mode settings."""
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

        updated_data = (
            self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        )
        self.assertEqual(updated_data["dark_mode"], True)
        self.assertEqual(updated_data["duprRating"], 5.5)

    def _setup_dashboard_mocks(self) -> None:
        """Set up specific mock data for dashboard tests."""
        self.mock_db.collection("users").document(MOCK_USER_ID).set(
            {
                "username": "user1",
                "stats": {"wins": 10, "losses": 5},
            }
        )

    @patch("pickaladder.user.services.dashboard.get_user_matches")
    def test_api_dashboard_fetches_matches_with_limit(
        self, mock_get_matches: MagicMock
    ) -> None:
        """Test that matches are fetched with limit."""
        self._set_session_user()
        self._setup_dashboard_mocks()
        mock_get_matches.return_value = []

        self.client.get("/user/api/dashboard")
        self.assertTrue(mock_get_matches.called)

    def test_api_dashboard_returns_group_match_flag(self) -> None:
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()
        self._setup_dashboard_mocks()

        match_data = {
            "matchType": "singles",
            "participants": [MOCK_USER_ID, "user2"],
            "player1Ref": self.mock_db.collection("users").document(MOCK_USER_ID),
            "player2Ref": self.mock_db.collection("users").document("user2"),
            "player1Score": 10,
            "player2Score": 5,
            "matchDate": datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            "groupId": "group123",
        }
        self.mock_db.collection("matches").add(match_data)
        self.mock_db.collection("users").document("user2").set({"username": "user2"})

        response = self.client.get("/user/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["matches"][0]["is_group_match"])

    @patch("pickaladder.user.routes.render_template")
    def test_view_user_includes_doubles_and_processes_matches(
        self, mock_render_template: MagicMock
    ) -> None:
        """Test that view_user fetches and processes matches."""
        self._set_session_user()

        self.mock_db.collection("users").document(MOCK_PROFILE_USER_ID).set(
            {
                "username": "profile_user",
                "stats": {"wins": 10, "losses": 5},
            }
        )
        self.mock_db.collection("users").document("opponent_id").set(
            {"username": "opponent_user"}
        )

        match_data = {
            "matchDate": datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc),
            "player1Score": 11,
            "player2Score": 9,
            "player1Ref": self.mock_db.collection("users").document(
                MOCK_PROFILE_USER_ID
            ),
            "player2Ref": self.mock_db.collection("users").document("opponent_id"),
            "matchType": "singles",
            "participants": [MOCK_PROFILE_USER_ID, "opponent_id"],
        }
        self.mock_db.collection("matches").add(match_data)

        self.client.get(f"/user/{MOCK_PROFILE_USER_ID}")

        _, kwargs = mock_render_template.call_args
        self.assertTrue(kwargs.get("matches"))
        self.assertEqual(len(kwargs.get("matches")), 1)


if __name__ == "__main__":
    unittest.main()