import datetime
import unittest
from unittest.mock import MagicMock, patch

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
        """Set up the test case."""
        self.mock_firestore_service = MagicMock()
        self.mock_auth_service = MagicMock()
        self.mock_storage_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch(
                "firebase_admin.firestore.client",
                return_value=self.mock_firestore_service.client.return_value,
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
        mock_user_doc.update.assert_called()

    def test_update_profile_picture_upload(self) -> None:
        """Test uploading a profile picture."""
        self._set_session_user()
        self._mock_firestore_user()

        mock_bucket = self.mock_storage_service.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "name": "User One",
            "email": "user1@example.com",
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
        mock_bucket.blob.assert_called_with(f"profile_pictures/{MOCK_USER_ID}/test.png")
        mock_blob.upload_from_filename.assert_called()
        mock_blob.make_public.assert_called()

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
        self.assertIn(b"Settings updated!", response.data)
        update_call_args = mock_user_doc.update.call_args[0][0]
        self.assertEqual(update_call_args["dark_mode"], True)
        self.assertEqual(update_call_args["duprRating"], 5.5)

    def _setup_dashboard_mocks(self, mock_db: MagicMock) -> None:
        """Set up specific mocks for the dashboard API tests."""
        self.mock_users_coll = MagicMock()
        self.mock_matches_coll = MagicMock()
        self.mock_groups_coll = MagicMock()

        def collection_side_effect(name: str) -> MagicMock:
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
        self.mock_user_doc.get.return_value.to_dict.return_value = {
            "username": "user1",
            "stats": {"wins": 10, "losses": 5},
        }
        self.mock_users_coll.document.return_value = self.mock_user_doc

        # Friends/requests/groups mocks
        (
            self.mock_user_doc.collection.return_value.where.return_value.stream.return_value
        ) = []
        (
            self.mock_user_doc.collection.return_value.where.return_value.where.return_value.stream.return_value
        ) = []
        self.mock_groups_coll.where.return_value.stream.return_value = []

    @patch("pickaladder.user.services.dashboard.get_user_matches")
    def test_api_dashboard_fetches_matches_with_limit(
        self, mock_get_matches: MagicMock
    ) -> None:
        """Test that matches are fetched with limit."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        self._setup_dashboard_mocks(mock_db)
        mock_get_matches.return_value = []

        self.client.get("/user/api/dashboard")

        # Verify get_user_matches was called
        self.assertTrue(mock_get_matches.called)

    def test_api_dashboard_returns_group_match_flag(self) -> None:
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)

        mock_match = MagicMock()
        mock_match.id = "match1"
        mock_p2_ref = MagicMock()
        mock_p2_ref.id = "user2"
        mock_p2_ref.get.return_value.exists = True
        mock_p2_ref.get.return_value.to_dict.return_value = {"username": "user2"}

        mock_match.to_dict.return_value = {
            "matchType": "singles",
            "participants": [MOCK_USER_ID, "user2"],
            "player1Ref": self.mock_user_doc,
            "player2Ref": mock_p2_ref,
            "player1Score": 10,
            "player2Score": 5,
            "matchDate": datetime.datetime(2023, 1, 1),
            "groupId": "group123",
        }

        mock_query = MagicMock()
        self.mock_matches_coll.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = [mock_match]

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

        mock_profile_user_ref = MagicMock()
        mock_profile_user_ref.id = MOCK_PROFILE_USER_ID
        mock_profile_user_ref.get.return_value.exists = True
        mock_profile_user_ref.get.return_value.to_dict.return_value = {
            "username": "profile_user",
            "stats": {"wins": 10, "losses": 5},
        }

        mock_matches_coll = MagicMock()

        def collection_side_effect(name: str) -> MagicMock:
            if name == "users":
                mock_users_coll = MagicMock()
                mock_users_coll.document.return_value = mock_profile_user_ref
                return mock_users_coll
            if name == "matches":
                return mock_matches_coll
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        mock_match = MagicMock()
        mock_match.id = "match1"
        mock_p2_ref = MagicMock()
        mock_p2_ref.id = "opponent_id"

        mock_match.to_dict.return_value = {
            "matchDate": datetime.datetime(2023, 1, 1),
            "player1Score": 11,
            "player2Score": 9,
            "player1Ref": mock_profile_user_ref,
            "player2Ref": mock_p2_ref,
            "matchType": "singles",
            "participants": [MOCK_PROFILE_USER_ID, "opponent_id"],
        }

        mock_query = MagicMock()
        mock_matches_coll.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream.return_value = [mock_match]

        mock_opponent_doc = MagicMock()
        mock_opponent_doc.id = "opponent_id"
        mock_opponent_doc.exists = True
        mock_opponent_doc.to_dict.return_value = {"username": "opponent_user"}

        mock_profile_doc = MagicMock()
        mock_profile_doc.id = MOCK_PROFILE_USER_ID
        mock_profile_doc.exists = True
        mock_profile_doc.to_dict.return_value = {
            "username": "profile_user",
            "stats": {"wins": 10, "losses": 5},
        }

        mock_db.get_all.return_value = [mock_profile_doc, mock_opponent_doc]

        self.client.get(f"/user/{MOCK_PROFILE_USER_ID}")

        args, kwargs = mock_render_template.call_args
        matches = kwargs.get("matches")
        self.assertTrue(matches)
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
