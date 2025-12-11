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

    def _setup_dashboard_mocks(self, mock_db):
        """Set up specific mocks for the dashboard API tests."""
        self.mock_users_coll = MagicMock()
        self.mock_matches_coll = MagicMock()
        self.mock_groups_coll = MagicMock()

        def collection_side_effect(name):
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

    def test_api_dashboard_fetches_all_matches_for_sorting(self):
        """Test that all matches are fetched (no limit) to allow correct in-memory sorting."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        self._setup_dashboard_mocks(mock_db)

        mock_query_where = MagicMock()
        self.mock_matches_coll.where.return_value = mock_query_where
        mock_query_where.stream.return_value = []

        # We also need to mock the path where limit IS called, to avoid crash if it is called
        mock_query_limit = MagicMock()
        mock_query_where.limit.return_value = mock_query_limit
        mock_query_limit.stream.return_value = []

        self.client.get("/user/api/dashboard")

        # Assert that limit was NOT called on the query
        self.assertFalse(
            mock_query_where.limit.called,
            "limit() should not be called on match queries",
        )
        self.assertFalse(
            mock_query_where.order_by.called,
            "order_by() should not be called (avoids composite index)",
        )

    def test_api_dashboard_returns_group_match_flag(self):
        """Test that the response includes an indicator for group matches."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        self._setup_dashboard_mocks(mock_db)

        # Construct a mock match with groupId
        mock_match = MagicMock()
        mock_match.id = "match1"
        mock_p2_ref = MagicMock()
        mock_p2_ref.id = "user2"
        mock_p2_ref.get.return_value.exists = True
        mock_p2_ref.get.return_value.to_dict.return_value = {"username": "user2"}

        mock_match.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": self.mock_user_doc,  # User is player 1
            "player2Ref": mock_p2_ref,
            "player1Score": 10,
            "player2Score": 5,
            "matchDate": "2023-01-01",
            "groupId": "group123",  # This makes it a group match
        }

        mock_stream = [mock_match]

        # Mock for the code path without limit (where -> stream)
        self.mock_matches_coll.where.return_value.stream.return_value = mock_stream

        response = self.client.get("/user/api/dashboard")

        self.assertEqual(response.status_code, 200)
        data = response.json
        matches = data["matches"]
        self.assertEqual(len(matches), 1)
        self.assertIn(
            "is_group_match", matches[0], "is_group_match field missing in response"
        )
        self.assertTrue(matches[0]["is_group_match"], "is_group_match should be True")


if __name__ == "__main__":
    unittest.main()
