import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

# INSIGHT #2: Explicitly import submodules to defeat lazy loading
# and ensure patch targets exist before the test runner tries to find them.

from pickaladder import create_app
from pickaladder.constants import USER_ID
import firebase_admin.auth

# Mock user payloads for consistent test data
MOCK_USER_ID = "user1"
MOCK_FIREBASE_TOKEN_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_FIRESTORE_USER_DATA = {"name": "User One", "isAdmin": True, "uid": "user1"}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test client and mock the necessary Firebase services."""
        # Patching where the object is looked up is the correct approach.
        # The pre-imports at the top of the file ensure these targets exist.
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            # The before_request hook looks up `auth` on the `firebase_admin` module
            # that was imported into the `pickaladder` namespace.
            "auth": patch("firebase_admin.auth"),
            # It also looks up `firestore` directly.
            "firestore_init": patch("pickaladder.firestore"),
            # The login route also uses firestore directly.
            "firestore_auth": patch("pickaladder.auth.routes.firestore"),
            # The user routes file looks up `firestore`, `storage`, and `uuid`.
            "firestore_user": patch("pickaladder.user.routes.firestore"),
            "storage": patch("pickaladder.user.routes.storage"),
            "uuid": patch("pickaladder.user.routes.uuid"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        # To ensure all parts of the app use the same mock firestore client,
        # we configure them to use the same MagicMock instance.
        self.mock_firestore_client = MagicMock()
        self.mocks["firestore_init"].client = self.mock_firestore_client
        self.mocks["firestore_auth"].client = self.mock_firestore_client
        self.mocks["firestore_user"].client = self.mock_firestore_client

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )

    def _get_logged_in_client(self):
        """
        Returns a test client with a fully simulated login state, satisfying both
        the session-based decorator and the token-based user loader.
        """
        # Configure mocks to handle token verification and user lookup.
        self.mocks["auth"].verify_id_token.return_value = MOCK_FIREBASE_TOKEN_PAYLOAD

        mock_db = self.mock_firestore_client.return_value
        mock_users_collection = mock_db.collection.return_value
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = MOCK_FIRESTORE_USER_DATA
        mock_users_collection.document.return_value.get.return_value = mock_user_doc

        # The login route checks for an admin, so we mock that to avoid a redirect to /install.
        mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = [
            MagicMock()
        ]

        client = self.app.test_client()
        with client.session_transaction() as sess:
            # INSIGHT #1: Satisfy the @login_required decorator's session check.
            sess[USER_ID] = MOCK_USER_ID

        return client

    def test_dashboard_loads(self):
        """Test that the dashboard loads for an authenticated user."""
        client = self._get_logged_in_client()
        headers = {"Authorization": "Bearer mock-token"}
        response = client.get("/user/dashboard", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)

    def test_update_profile_data(self):
        """Test updating user profile data."""
        client = self._get_logged_in_client()
        headers = {"Authorization": "Bearer mock-token"}

        response = client.post(
            "/user/update_profile",
            headers=headers,
            data={"dark_mode": "y", "duprRating": 5.5},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        self.mock_firestore_client.return_value.collection("users").document(
            MOCK_USER_ID
        ).update.assert_called_once()

    def test_update_profile_picture_upload(self):
        """Test successfully uploading a profile picture."""
        client = self._get_logged_in_client()
        headers = {"Authorization": "Bearer mock-token"}

        mock_storage = self.mocks["storage"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        self.mocks["uuid"].uuid4.return_value.hex = "test-uuid"

        data = {"profile_picture": (BytesIO(b"test_image_data"), "test.png")}
        response = client.post(
            "/user/update_profile",
            headers=headers,
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Profile updated successfully.", response.data)
        mock_bucket.blob.assert_called_with(
            f"profile-pictures/{MOCK_USER_ID}/original_test-uuid.jpg"
        )
        mock_blob.upload_from_file.assert_called_once()
        self.mock_firestore_client.return_value.collection("users").document(
            MOCK_USER_ID
        ).update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
