import datetime
import unittest
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app

# Mock user payloads for consistent test data
MOCK_USER_ID = "user1"
MOCK_PROFILE_USER_ID = "user2"
MOCK_FIREBASE_TOKEN_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_FIRESTORE_USER_DATA = {
    "name": "User One",
    "email": "user1@example.com",
    "isAdmin": True,
    "uid": "user1",
    "stats": {"wins": 10, "losses": 5},
}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for user routes with Firebase mocks using MockFirestore."""

    mock_db: MockFirestore
    mock_firestore_service: MagicMock
    mock_auth_service: MagicMock
    mock_storage_service: MagicMock
    patcher_firestore: Any
    patcher_field_filter: Any
    mock_field_filter_class: MagicMock
    patcher_auth: Any
    mock_auth: MagicMock
    patcher_storage: Any
    mock_storage: MagicMock
    patcher_init: Any

    def setUp(self) -> None:
        """Set up the test case with MockFirestore and service patches."""
        self.mock_db = MockFirestore()
        self.mock_firestore_service = MagicMock()
        self.mock_auth_service = MagicMock()
        self.mock_auth_service.EmailAlreadyExistsError = type(
            "EmailAlreadyExistsError", (Exception,), {}
        )
        self.mock_storage_service = MagicMock()

        self.mock_firestore_service.client.return_value = self.mock_db

        self.patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch(
                "firebase_admin.firestore.client",
                return_value=self.mock_db,
            ),
            "auth_core": patch(
                "pickaladder.user.services.core.auth", new=self.mock_auth_service
            ),
            "auth_profile": patch(
                "pickaladder.user.services.profile.auth", new=self.mock_auth_service
            ),
            "storage_core": patch(
                "pickaladder.user.services.core.storage", new=self.mock_storage_service
            ),
            "storage_profile": patch(
                "pickaladder.user.services.profile.storage",
                new=self.mock_storage_service,
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
            "send_email": patch("pickaladder.user.services.core.send_email"),
        }

        for name, p in self.patchers.items():
            m = p.start()
            if name == "auth":
                m.EmailAlreadyExistsError = (
                    self.mock_auth_service.EmailAlreadyExistsError
                )

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
        self.mock_auth.EmailAlreadyExistsError = (
            self.mock_auth_service.EmailAlreadyExistsError
        )

        self.patcher_storage = patch("firebase_admin.storage")
        self.mock_storage = self.patcher_storage.start()

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers."""
        for p in self.patchers.values():
            p.stop()
        self.patcher_field_filter.stop()
        self.patcher_auth.stop()
        self.patcher_storage.stop()

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and populate mock Firestore."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Setup the user in mock DB so loaders find it
        self.mock_db.collection("users").document(user_id).set({
            "username": "user1",
            "email": "user1@example.com",
            "name": "User One",
            "uid": user_id,
            "stats": {
                "wins": 10,
                "losses": 5,
                "total_games": 15,
                "win_rate": 66.7,
                "current_streak": 2,
                "streak_type": "win",
            },
        })

    def test_settings_get(self) -> None:
        """Test that the settings page loads for a logged-in user."""
        self._set_session_user()
        
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

        user_doc = (
            self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        )
        self.assertEqual(user_doc["name"], "New Name")
        self.assertEqual(user_doc["username"], "newuser")

    def test_update_profile_picture_upload(self) -> None:
        """Test uploading a profile picture."""
        self._set_session_user()

        mock_bucket = self.mock_storage_service.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "profile_picture": (BytesIO(b"test_image_data"), "test.png"),
            "username": "newuser",
            "name": "New User",
            "email": "newuser@example.com",
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

        user_doc = (
            self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        )
        self.assertEqual(user_doc["dark_mode"], True)
        self.assertEqual(user_doc["duprRating"], 5.5)

    @patch("pickaladder.user.services.dashboard.get_user_matches")
    def test_api_dashboard_fetches_matches_with_limit(
        self, mock_get_matches: MagicMock
    ) -> None:
        """Test that matches are fetched with limit."""
        self._set_session_user()
        mock_get_matches.return_value = []

        self.client.get("/user/api/dashboard")
        self.assertTrue(mock_get_matches.called)

    def test_api_dashboard_returns_group_match_flag(self) -> None:
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()

        self.mock_db.collection("matches").document("match1").set({
            "matchType": "singles",
            "participants": [MOCK_USER_ID, "user2"],
            "player1Ref": self.mock_db.collection("users").document(MOCK_USER_ID),
            "player2Ref": self.mock_db.collection("users").document("user2"),
            "player1Score": 10,
            "player2Score": 5,
            "matchDate": datetime.datetime(2023, 1, 1),
            "groupId": "group123",
            "createdAt": datetime.datetime.now(),
        })

        self.mock_db.collection("users").document("user2").set(
            {"username": "user2", "name": "User Two"}
        )

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
        """Test that view_user fetches and processes matches."""
        self._set_session_user()

        self.mock_db.collection("users").document(MOCK_PROFILE_USER_ID).set({
            "username": "profile_user",
            "stats": {"wins": 10, "losses": 5},
        })
        self.mock_db.collection("users").document("opponent_id").set(
            {"username": "opponent_user", "name": "Opponent User"}
        )

        self.mock_db.collection("matches").document("match1").set({
            "matchDate": datetime.datetime(2023, 1, 1),
            "player1Score": 11,
            "player2Score": 9,
            "player1Ref": self.mock_db.collection("users").document(MOCK_PROFILE_USER_ID),
            "player2Ref": self.mock_db.collection("users").document("opponent_id"),
            "matchType": "singles",
            "participants": [MOCK_PROFILE_USER_ID, "opponent_id"],
            "createdAt": datetime.datetime.now(),
        })

        self.client.get(f"/user/{MOCK_PROFILE_USER_ID}")

        args, kwargs = mock_render_template.call_args
        matches = kwargs.get("matches")
        self.assertTrue(matches)
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()