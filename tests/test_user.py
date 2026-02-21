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
    "isAdmin": True,
    "uid": "user1",
    "stats": {"wins": 10, "losses": 5},
}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for user routes with Firebase mocks."""

    def setUp(self) -> None:
        """Set up the test case using structured patchers."""
        # RESOLVED: Use MockFirestore from jules branch for better query support
        self.mock_db = MockFirestore()
        self.mock_auth_service = MagicMock()
        self.mock_auth_service.EmailAlreadyExistsError = type(
            "EmailAlreadyExistsError", (Exception,), {}
        )
        self.mock_storage_service = MagicMock()

        # RESOLVED: Adopt patchers_dict from main branch for clean setup/teardown
        self.patchers_dict = {
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
        
        for name, p in self.patchers_dict.items():
            p.start()

        # Patch FieldFilter for SDK compatibility
        self.patcher_field_filter = patch("firebase_admin.firestore.FieldFilter")
        self.mock_field_filter_class = self.patcher_field_filter.start()

        def field_filter_side_effect(field, op, value):
            mock = MagicMock()
            mock.field_path = field
            mock.op_string = op
            mock.value = value
            return mock

        self.mock_field_filter_class.side_effect = field_filter_side_effect

        # Initialize MockFirestore helper from jules branch
        patch_mockfirestore()

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Stop all patchers structured in setup."""
        for p in self.patchers_dict.values():
            p.stop()
        self.patcher_field_filter.stop()

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and setup mock doc."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

        # Setup the user in mock DB so user_loader finds it
        self.mock_db.collection("users").document(user_id).set({
            "username": "user1",
            "email": "user1@example.com",
            "name": "User One",
            "uid": user_id,
            "stats": {"wins": 0, "losses": 0},
        })

    # ... (Test methods like test_settings_get and test_settings_post_success follow)

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
        
        # Verify the update in MockFirestore
        updated_data = self.mock_db.collection("users").document(MOCK_USER_ID).get().to_dict()
        self.assertEqual(updated_data["username"], "newuser")

    # ... (remaining tests like test_update_profile_picture_upload remain unchanged)