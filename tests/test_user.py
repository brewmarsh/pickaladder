import datetime
import unittest
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

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
        """Set up the test case."""
        self.mock_db = MagicMock()
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
            patch("pickaladder.user.services.core.storage", new=self.mock_storage_service),
            patch("pickaladder.user.services.profile.storage", new=self.mock_storage_service),
            patch("firebase_admin.auth.verify_id_token", return_value=MOCK_FIREBASE_TOKEN_PAYLOAD),
            patch("firebase_admin.auth"),
            patch("firebase_admin.storage"),
            patch("pickaladder.user.services.core.send_email"),
            patch("firebase_admin.firestore.FieldFilter")
        ]

        self.started_patches = [p.start() for p in self.patches]
        self.mock_field_filter_class = self.started_patches[-1]

        def field_filter_side_effect(field, op, value):
            mock = MagicMock()
            mock.field_path = field
            mock.op_string = op
            mock.value = value
            return mock

        self.mock_field_filter_class.side_effect = field_filter_side_effect

        self.app = create_app()
        self.app.config.update({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False
        })
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers."""
        for p in self.patches:
            p.stop()

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and populate mock DB."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
        
        # Populate the mock DB so the application's user-loader can find the user
        self.mock_db.collection("users").document(user_id).get().to_dict.return_value = MOCK_FIRESTORE_USER_DATA

    def _mock_firestore_user(self, user_id: str = MOCK_USER_ID, data: dict[Any, Any] | None = None) -> Any:
        """Setup a mock user document in Firestore and return the reference."""
        if data is None:
            data = MOCK_FIRESTORE_USER_DATA
        doc_ref = self.mock_db.collection("users").document(user_id)
        doc_ref.get().to_dict.return_value = data
        return doc_ref

    def test_settings_get(self) -> None:
        """Test that the settings page loads for a logged-in user."""
        self._set_session_user()
        response = self.client.get("/user/settings")
        self.assertEqual(response.status_code, 200)

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