import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

# INSIGHT #2: Explicitly import submodules to defeat lazy loading
# and ensure patch targets exist before the test runner tries to find them.

from pickaladder import create_app

# Mock user payloads for consistent test data
MOCK_USER_ID = "user1"
MOCK_FIREBASE_TOKEN_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_FIRESTORE_USER_DATA = {"name": "User One", "isAdmin": True, "uid": "user1"}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_firestore_service = MagicMock()
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch("pickaladder.user.routes.firestore", new=self.mock_firestore_service),
            "storage": patch("pickaladder.user.routes.storage"),
            "uuid": patch("pickaladder.user.routes.uuid"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost",
                "LOGIN_DISABLED": True,
            }
        )
        self.client = self.app.test_client()

    def test_dashboard_loads(self):
        """Test that the dashboard loads for an authenticated user."""
        response = self.client.get("/user/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)

    def test_update_profile_data(self):
        """Test updating user profile data."""
        response = self.client.post(
            "/user/update_profile",
            data={"dark_mode": "y", "duprRating": 5.5},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        self.mock_firestore_service.client.return_value.collection("users").document(
            "test_user_id"
        ).update.assert_called_once()

    def test_update_profile_picture_upload(self):
        """Test successfully uploading a profile picture."""
        mock_storage = self.mocks["storage"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        self.mocks["uuid"].uuid4.return_value.hex = "test-uuid"

        data = {"profile_picture": (BytesIO(b"test_image_data"), "test.png")}
        response = self.client.post(
            "/user/update_profile",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        mock_bucket.blob.assert_called_with(
            f"profile-pictures/test_user_id/original_test-uuid.jpg"
        )
        mock_blob.upload_from_file.assert_called_once()
        self.mock_firestore_service.client.return_value.collection("users").document(
            "test_user_id"
        ).update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
