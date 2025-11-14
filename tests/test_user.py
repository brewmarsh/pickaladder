"""Tests for the user blueprint."""

import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

# INSIGHT #2: Explicitly import submodules to defeat lazy loading
# and ensure patch targets exist before the test runner tries to find them.
from pickaladder import create_app

# Mock user payloads for consistent test data
MOCK_USER_ID = "user1"
MOCK_FIREBASE_TOKEN_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_FIRESTORE_USER_DATA = {"name": "User One", "isAdmin": True, "uid": "user1"}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the user blueprint."""

    def setUp(self):
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_firestore_service = MagicMock()
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "storage": patch("pickaladder.user.routes.storage"),
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

    def tearDown(self):
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_FIREBASE_TOKEN_PAYLOAD

    def _mock_firestore_user(self):
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_FIRESTORE_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot
        return mock_user_doc

    def test_dashboard_loads(self):
        """Test that the dashboard loads for an authenticated user."""
        self._set_session_user()
        self._mock_firestore_user()

        response = self.client.get("/user/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)

    def test_update_profile_data(self):
        """Test updating user profile data."""
        self._set_session_user()
        mock_user_doc = self._mock_firestore_user()

        response = self.client.post(
            "/user/dashboard",
            data={"dark_mode": "y", "dupr_rating": 5.5},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        mock_user_doc.update.assert_called_once()

    def test_update_profile_picture_upload(self):
        """Test successfully uploading a profile picture."""
        self._set_session_user()
        mock_user_doc = self._mock_firestore_user()
        mock_storage = self.mocks["storage"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {"profile_picture": (BytesIO(b"test_image_data"), "test.png")}
        response = self.client.post(
            "/user/dashboard",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        mock_storage.bucket.assert_called_once()
        mock_bucket.blob.assert_called_once_with(
            f"profile_pictures/{MOCK_USER_ID}/test.png"
        )
        mock_blob.upload_from_filename.assert_called_once()
        mock_blob.make_public.assert_called_once()
        self.assertEqual(
            mock_user_doc.update.call_args[0][0]["profilePictureUrl"],
            "https://storage.googleapis.com/test-bucket/test.jpg",
        )

    def test_update_dupr_and_dark_mode(self):
        """Test updating DUPR rating and dark mode settings."""
        self._set_session_user()
        mock_user_doc = self._mock_firestore_user()

        response = self.client.post(
            "/user/dashboard",
            data={"dark_mode": "y", "dupr_rating": "5.5"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        mock_user_doc.update.assert_called_once_with(
            {"dark_mode": True, "duprRating": 5.5}
        )


if __name__ == "__main__":
    unittest.main()
