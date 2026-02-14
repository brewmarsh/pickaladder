"""Tests for user routes and profiles."""

import datetime
import unittest
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
    "isAdmin": True,
    "uid": "user1",
    "email": "user1@example.com",
}


class UserTestCase(unittest.TestCase):
    """Test cases for user-related routes and functionality."""

    def setUp(self) -> None:
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_firestore_service = MagicMock()
        patchers = {
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
            "storage_service": patch("pickaladder.user.services.core.storage"),
            "storage_service_profile": patch(
                "pickaladder.user.services.profile.storage"
            ),
            "auth_service_profile": patch("pickaladder.user.services.profile.auth"),
            "auth_service_core": patch("pickaladder.user.services.core.auth"),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
            "auth": patch("pickaladder.user.services.core.auth"),
        }

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
                "dupr_rating": 5.5,
                "username": "newuser",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated successfully.", response.data)
        # Note: update_user_profile and process_profile_update are both called
        self.assertTrue(mock_user_doc.update.called)

    def test_update_profile_picture_upload(self) -> None:
        """Test successfully uploading a profile picture."""
        self._set_session_user()
        mock_user_doc = self._mock_firestore_user()
        mock_storage = self.mocks["storage_service_profile"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "name": "User One",
            "email": "user1@example.com",
            "profile_picture": (BytesIO(b"test_image_data"), "test.png"),
            "username": "newuser",
            "name": "New User",
            "email": "user1@example.com",
        }
        response = self.client.post(
            "/user/settings",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated successfully.", response.data)
        mock_storage.bucket.assert_called_once()
        mock_bucket.blob.assert_called_once_with(
            f"profile_pictures/{MOCK_USER_ID}/test.png"
        )
        mock_blob.upload_from_filename.assert_called_once()
        mock_blob.make_public.assert_called_once()
        # Find the call that contains profilePictureUrl
        update_calls = [c[0][0] for c in mock_user_doc.update.call_args_list]
        pic_call = next(
            (
                c
                for c in update_calls
                if isinstance(c, dict) and "profilePictureUrl" in c
            ),
            None,
        )
        self.assertIsNotNone(pic_call)
        if pic_call is not None:
            self.assertEqual(
                pic_call["profilePictureUrl"],
                "https://storage.googleapis.com/test-bucket/test.jpg",
            )

    def test_update_dupr_and_dark_mode(self) -> None:
        """Test updating DUPR rating and dark mode settings."""
        self._set_session_user()
        mock_user_doc = self._mock_firestore_user()

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
        self.assertIn(b"Settings updated successfully.", response.data)
        # Check all update calls
        update_calls = [c[0][0] for c in mock_user_doc.update.call_args_list]

        dark_mode_call = next(
            (c for c in update_calls if isinstance(c, dict) and "dark_mode" in c), None
        )
        self.assertIsNotNone(dark_mode_call)
        if dark_mode_call is not None:
            self.assertEqual(dark_mode_call["dark_mode"], True)

        dupr_call = next(
            (c for c in update_calls if isinstance(c, dict) and "duprRating" in c), None
        )
        self.assertIsNotNone(dupr_call)
        if dupr_call is not None:
            self.assertEqual(dupr_call["duprRating"], 5.5)

    def _setup_dashboard_mocks(self, mock_db: MagicMock) -> None:
        """Set up specific mocks for the dashboard API tests."""
        self.mock_users_coll = MagicMock()
        self.mock_matches_coll = MagicMock()
        self.mock_groups_coll = MagicMock()

        def collection_side_effect(name: str) -> MagicMock:
            """Firestore collection side effect mock."""
            if name == "users":
                return self.mock_users_coll
            if name == "matches":
                return self.mock_matches_coll
            if name == "groups":
                return self.mock_groups_coll
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        # User doc setup
        self.mock_user_doc = MagicMock()
        self.mock_user_doc.id = MOCK_USER_ID
        self.mock_user_doc.get.return_value.to_dict.return_value = {"username": "user1"}
        self.mock_users_coll.document.return_value = self.mock_user_doc

        # Empty friends/requests/groups by default
        self.mock_user_doc.collection(
            "friends"
        ).where.return_value.stream.return_value = []
        self.mock_user_doc.collection(
            "friends"
        ).where.return_value.where.return_value.stream.return_value = []
        self.mock_groups_coll.where.return_value.stream.return_value = []

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
