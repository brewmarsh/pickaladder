"""Unit tests for user blueprint."""

import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from pickaladder import create_app

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
}


class TestUserRoutes(unittest.TestCase):
    """Test user routes."""

    def setUp(self) -> None:
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_firestore_service = MagicMock()
        self.patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_utils": patch(
                "pickaladder.user.services.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "storage_service": patch("pickaladder.user.services.profile.storage"),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }
        for p in self.patchers.values():
            p.start()
        
        self.mocks = {k: p.new for k, p in self.patchers.items()}
        
        # Configure the mock Firestore client
        self.mock_db = self.mock_firestore_service.client.return_value
        
        # Setup app
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patches."""
        for p in self.patchers.values():
            p.stop()

    def _set_session_user(self) -> None:
        """Simulate a logged-in user."""
        # We need to mock g.user somehow or simulate session
        # Since using Flask-Login or similar, usually we define a user loader or similar.
        # But looking at routes, it uses @login_required decorator.
        # The decorator likely checks session or verify_id_token.
        # For simplicity in this reconstruction, we'll rely on the auth mocking which might happen in create_app or decorators.
        # Actually, let's look at how the test was running. It was likely using session injection.
        
        # Mocking verify_id_token to return our payload
        self.mocks["verify_id_token"].return_value = MOCK_FIREBASE_TOKEN_PAYLOAD
        
        # We also need to mock the user loading in the request context
        # But standard pattern is:
        with self.client.session_transaction() as sess:
            sess["user"] = MOCK_FIREBASE_TOKEN_PAYLOAD

    def _mock_firestore_user(self) -> MagicMock:
        """Mock the user document in Firestore."""
        mock_user_ref = MagicMock()
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = MOCK_FIRESTORE_USER_DATA
        mock_user_ref.get.return_value = mock_user_doc
        
        # Mock collection("users").document(uid)
        def collection_side_effect(name):
            if name == "users":
                col_mock = MagicMock()
                col_mock.document.return_value = mock_user_ref
                return col_mock
            return MagicMock()

        self.mock_db.collection.side_effect = collection_side_effect
        return mock_user_ref

    def test_update_settings(self) -> None:
        """Test updating user settings."""
        self._set_session_user()
        mock_user_ref = self._mock_firestore_user()
        
        response = self.client.post(
            "/user/settings",
            data={
                "name": "User One",
                "email": "user1@example.com",
                "dark_mode": "y",
                "dupr_rating": 5.5,
                "username": "newuser",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated successfully.", response.data)
        # Note: update_settings now calls update multiple times in the new route
        self.assertTrue(mock_user_ref.update.called)

    def test_update_profile_picture_upload(self) -> None:
        """Test successfully uploading a profile picture."""
        self._set_session_user()
        self._mock_firestore_user()
        mock_storage = self.mocks["storage_service"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "name": "User One",
            "email": "user1@example.com",
            "profile_picture": (BytesIO(b"test_image_data"), "test.png"),
            "username": "newuser",
        }
        response = self.client.post(
            "/user/settings",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated successfully.", response.data)
        mock_storage.bucket.assert_called()
        mock_bucket.blob.assert_called_with(f"profile_pictures/{MOCK_USER_ID}/test.png")
        mock_blob.upload_from_filename.assert_called_once()
        mock_blob.make_public.assert_called_once()