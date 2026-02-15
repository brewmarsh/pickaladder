import datetime
import unittest
from io import BytesIO
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
    "username": "user1",
}


class UserRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for user routes with Firebase mocks."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.mock_firestore_service = MagicMock()
        self.mock_db = self.mock_firestore_service.client.return_value

        self.mock_auth_service = MagicMock()
        # Define EmailAlreadyExistsError to allow catching it
        self.mock_auth_service.EmailAlreadyExistsError = type(
            "EmailAlreadyExistsError", (Exception,), {}
        )

        self.mock_storage_service = MagicMock()

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
            "field_filter": patch("firebase_admin.firestore.FieldFilter"),
        }

        self.mocks = {name: p.start() for name, p in self.patchers.items()}
        for p in self.patchers.values():
            self.addCleanup(p.stop)

        def field_filter_side_effect(field, op, value):
            mock = MagicMock()
            mock.field_path = field
            mock.op_string = op
            mock.value = value
            return mock

        self.mocks["field_filter"].side_effect = field_filter_side_effect

        patch_mockfirestore()

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Tear down after tests."""
        pass

    def _set_session_user(self, user_id: str = MOCK_USER_ID) -> None:
        """Set the user ID in the session and setup mock doc."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
        self.mocks["verify_id_token"].return_value = MOCK_FIREBASE_TOKEN_PAYLOAD

        # Also need to mock the user doc for before_request
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = MOCK_FIRESTORE_USER_DATA
        self.mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_user_doc
        )

    def _mock_firestore_user(self) -> MagicMock:
        """Helper to mock a user document in Firestore."""
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = MOCK_FIRESTORE_USER_DATA
        self.mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_user_doc
        )
        return mock_user_doc

    def test_settings_get(self) -> None:
        """Test retrieving the settings page."""
        self._set_session_user()
        self._mock_firestore_user()

        response = self.client.get("/user/settings")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account Settings", response.data)

    def test_settings_post_success(self) -> None:
        """Test successfully updating settings."""
        self._set_session_user()
        self._mock_firestore_user()

        # Setup the document reference mock to catch the update call
        mock_user_ref = self.mock_db.collection.return_value.document.return_value

        data = {
            "username": "user1",
            "dark_mode": "y",
            "dupr_rating": "4.5",
            "email": "user1@example.com",
            "name": "User One",
        }
        response = self.client.post(
            "/user/settings",
            data=data,
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)
        mock_user_ref.update.assert_called()

    def test_update_profile_picture_upload(self) -> None:
        """Test uploading a profile picture."""
        self._set_session_user()
        self._mock_firestore_user()

        mock_bucket = self.mock_storage_service.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "https://storage.googleapis.com/test-bucket/test.jpg"

        data = {
            "profile_picture": (BytesIO(b"test_image_data"), "test.png"),
            "username": "user1",
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
        self.assertIn(b"Settings updated!", response.data)

    def test_update_dupr_and_dark_mode(self) -> None:
        """Test updating DUPR rating and dark mode settings."""
        self._set_session_user()
        self._mock_firestore_user()
        mock_user_ref = self.mock_db.collection.return_value.document.return_value

        data = {
            "username": "user1",
            "dupr_rating": "3.5",
            "dark_mode": "y",
            "email": "user1@example.com",
            "name": "User One",
        }
        response = self.client.post(
            "/user/settings",
            data=data,
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Settings updated!", response.data)

        # Check if Firestore was updated with correct fields
        update_call_args = mock_user_ref.update.call_args[0][0]
        self.assertEqual(update_call_args["dupr_rating"], 3.5)
        self.assertEqual(update_call_args["duprRating"], 3.5)
        self.assertTrue(update_call_args["dark_mode"])

    def test_api_dashboard_returns_group_match_flag(self) -> None:
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()

        mock_match = MagicMock()
        mock_match.id = "match1"
        mock_match.to_dict.return_value = {
            "player1Ref": MagicMock(id=MOCK_USER_ID),
            "player2Ref": MagicMock(id="other_user"),
            "player1Score": 11,
            "player2Score": 9,
            "matchDate": datetime.datetime.now(),
            "groupId": "some_group_id",
            "matchType": "singles",
            "participants": [MOCK_USER_ID, "other_user"],
        }

        mock_matches_query = MagicMock()
        # Mocking the chain: where().order_by().limit().stream()
        mock_matches_query.where.return_value = mock_matches_query
        mock_matches_query.order_by.return_value = mock_matches_query
        mock_matches_query.limit.return_value = mock_matches_query
        mock_matches_query.stream.return_value = [mock_match]

        def collection_side_effect(name: str) -> MagicMock:
            if name == "matches":
                return mock_matches_query
            return MagicMock()

        self.mock_db.collection.side_effect = collection_side_effect

        response = self.client.get("/match/history")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["matches"][0]["is_group_match"])

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
            "uid": MOCK_PROFILE_USER_ID,
        }

        mock_matches_coll = MagicMock()
        mock_matches_coll.where.return_value = mock_matches_coll
        mock_matches_coll.order_by.return_value = mock_matches_coll
        mock_matches_coll.limit.return_value = mock_matches_coll

        def collection_side_effect(name: str) -> MagicMock:
            if name == "users":
                mock_users_coll = MagicMock()
                mock_users_coll.document.return_value = mock_profile_user_ref
                return mock_users_coll
            if name == "matches":
                return mock_matches_coll
            return MagicMock()

        self.mock_db.collection.side_effect = collection_side_effect

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
        mock_matches_coll.stream.return_value = [mock_match]

        mock_profile_doc = MagicMock()
        mock_profile_doc.exists = True
        mock_profile_doc.id = MOCK_PROFILE_USER_ID
        mock_profile_doc.to_dict.return_value = {
            "username": "profile_user",
            "uid": MOCK_PROFILE_USER_ID,
        }

        mock_opponent_doc = MagicMock()
        mock_opponent_doc.exists = True
        mock_opponent_doc.id = "opponent_id"
        mock_opponent_doc.to_dict.return_value = {
            "username": "opponent_user",
            "uid": "opponent_id",
        }

        self.mock_db.get_all.return_value = [mock_profile_doc, mock_opponent_doc]

        self.client.get(f"/user/{MOCK_PROFILE_USER_ID}")

        self.assertTrue(mock_render_template.called)
        context = mock_render_template.call_args[1]
        self.assertEqual(len(context["matches"]), 1)
        self.assertEqual(context["matches"][0]["user_result"], "win")


if __name__ == "__main__":
    unittest.main()
