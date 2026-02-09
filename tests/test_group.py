"""Tests for the group blueprint."""

from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Group Owner", "isAdmin": False}


class GroupRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the group blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_utils": patch(
                "pickaladder.group.utils.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "storage_routes": patch("pickaladder.group.routes.storage"),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
            "leaderboard": patch(
                "pickaladder.group.services.group_service.get_group_leaderboard",
                return_value=[],
            ),
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

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        """TODO: Add docstring for AI context."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self) -> dict[str, str]:
        """Get standard authentication headers for tests."""
        return {"Authorization": "Bearer mock-token"}

    def test_create_group(self) -> None:
        """Test successfully creating a new group."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_groups_collection = mock_db.collection("groups")
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_group_id"
        mock_groups_collection.add.return_value = (None, mock_doc_ref)

        mock_group_doc = mock_groups_collection.document("new_group_id")
        mock_group_snapshot = MagicMock()
        mock_group_snapshot.exists = True
        mock_group_snapshot.to_dict.return_value = {
            "name": "My Firebase Group",
            "ownerRef": mock_user_doc,
        }
        mock_group_doc.get.return_value = mock_group_snapshot

        response = self.client.post(
            "/group/create",
            headers=self._get_auth_headers(),
            data={"name": "My Firebase Group"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group created successfully.", response.data)
        mock_groups_collection.add.assert_called_once()
        call_args = mock_groups_collection.add.call_args[0]
        self.assertEqual(call_args[0]["name"], "My Firebase Group")

    def test_create_group_with_image(self) -> None:
        """Test successfully creating a new group with an image."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_groups_collection = mock_db.collection("groups")
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_group_id_img"
        mock_groups_collection.add.return_value = (None, mock_doc_ref)

        # Mock the new group ref update method (used for profilePictureUrl)
        mock_doc_ref.update = MagicMock()

        # Mock storage
        mock_storage = self.mocks["storage_routes"]
        mock_bucket = mock_storage.bucket.return_value
        mock_blob = mock_bucket.blob.return_value
        mock_blob.public_url = "http://mock-storage-url/img.jpg"

        mock_group_doc = mock_groups_collection.document("new_group_id_img")
        mock_group_snapshot = MagicMock()
        mock_group_snapshot.exists = True
        mock_group_snapshot.to_dict.return_value = {
            "name": "My Image Group",
            "ownerRef": mock_user_doc,
        }
        mock_group_doc.get.return_value = mock_group_snapshot

        # Create a mock file
        data = {
            "name": "My Image Group",
            "profile_picture": (BytesIO(b"fake image data"), "test.jpg"),
        }

        response = self.client.post(
            "/group/create",
            headers=self._get_auth_headers(),
            data=data,
            follow_redirects=True,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group created successfully.", response.data)

        # Verify add called
        mock_groups_collection.add.assert_called_once()

        # Verify storage interaction
        mock_bucket.blob.assert_called_with("group_pictures/new_group_id_img/test.jpg")
        mock_blob.upload_from_file.assert_called()
        mock_blob.make_public.assert_called()

        # Verify update called on doc_ref
        mock_doc_ref.update.assert_called_with(
            {"profilePictureUrl": "http://mock-storage-url/img.jpg"}
        )

    def test_get_rivalry_stats(self) -> None:
        """Test the head-to-head stats calculation."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        playerA_id = "p1"
        playerB_id = "p2"
        other_player1_id = "p3"
        other_player2_id = "p4"
        group_id = "test_group"

        # --- Mock Data ---
        # 1. p1/p2 are partners, they win
        match1 = MagicMock()
        match1.id = "match1"
        match1.to_dict.return_value = {
            "groupId": group_id,
            "player1Id": playerA_id,
            "partnerId": playerB_id,
            "player2Id": other_player1_id,
            "opponent2Id": other_player2_id,
            "winner": "team1",
            "team1Score": 11,
            "team2Score": 7,
        }
        # 2. p1/p2 are partners, they lose
        match2 = MagicMock()
        match2.id = "match2"
        match2.to_dict.return_value = {
            "groupId": group_id,
            "player1Id": other_player1_id,
            "partnerId": other_player2_id,
            "player2Id": playerA_id,
            "opponent2Id": playerB_id,
            "winner": "team1",
            "team1Score": 11,
            "team2Score": 9,
        }
        # 3. p1/p2 are opponents, p1 wins
        match3 = MagicMock()
        match3.id = "match3"
        match3.to_dict.return_value = {
            "groupId": group_id,
            "player1Id": playerA_id,
            "partnerId": other_player1_id,
            "player2Id": playerB_id,
            "opponent2Id": other_player2_id,
            "winner": "team1",
            "team1Score": 11,
            "team2Score": 5,
        }
        # 4. p1/p2 are opponents, p2 wins
        match4 = MagicMock()
        match4.id = "match4"
        match4.to_dict.return_value = {
            "groupId": group_id,
            "player1Id": playerA_id,
            "partnerId": other_player1_id,
            "player2Id": playerB_id,
            "opponent2Id": other_player2_id,
            "winner": "team2",
            "team1Score": 8,
            "team2Score": 11,
        }
        # 5. Match without both players (should be filtered out)
        match5 = MagicMock()
        match5.id = "match5"
        match5.to_dict.return_value = {
            "groupId": group_id,
            "player1Id": other_player1_id,
            "player2Id": other_player2_id,
        }

        mock_matches_query = mock_db.collection.return_value.where.return_value
        mock_matches_query.stream.return_value = [
            match1,
            match2,
            match3,
            match4,
            match5,
        ]

        response = self.client.get(
            f"/group/{group_id}/stats/rivalry?playerA_id={playerA_id}&playerB_id={playerB_id}",
            headers=self._get_auth_headers(),
        )

        self.assertEqual(response.status_code, 200)
        stats = response.get_json()
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["point_diff"], 3)
        self.assertEqual(len(stats["matches"]), 2)

    def test_get_rivalry_stats_missing_params(self) -> None:
        """Test head-to-head stats with missing player IDs."""
        self._set_session_user()
        response = self.client.get(
            "/group/some_group/stats/rivalry?playerA_id=p1",
            headers=self._get_auth_headers(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_view_group(self) -> None:
        """Test the view_group route and eligible friends logic."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        group_id = "test_group_id"

        # Mock user doc/snapshot
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        # Mock group doc/snapshot
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True
        mock_group_doc.id = group_id
        mock_group_doc.to_dict.return_value = {
            "name": "Test Group",
            "ownerRef": mock_user_doc,
            "members": [mock_user_doc],
        }
        mock_db.collection("groups").document(
            group_id
        ).get.return_value = mock_group_doc

        # Mock friends
        friend_id = "friend1"
        mock_friend_ref = mock_db.collection("users").document(friend_id)
        mock_friend_doc = MagicMock()
        mock_friend_doc.id = friend_id
        mock_friend_doc.exists = True
        mock_friend_doc.to_dict.return_value = {"name": "Friend One"}

        # Mocking the stream for friends query
        mock_friends_query = mock_user_doc.collection.return_value.where.return_value
        mock_friend_snapshot = MagicMock()
        mock_friend_snapshot.id = friend_id
        mock_friends_query.stream.return_value = [mock_friend_snapshot]

        # Mock db.get_all for eligible friends.
        mock_db.get_all.return_value = [mock_friend_doc]

        # Patch helpers to simplify
        with (
            patch(
                "pickaladder.group.services.group_service.GroupService._fetch_recent_matches",
                return_value=([], []),
            ),
            patch(
                "pickaladder.group.services.group_service.GroupService._fetch_group_teams",
                return_value=([], None),
            ),
        ):
            response = self.client.get(
                f"/group/{group_id}", headers=self._get_auth_headers()
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Group", response.data)
        self.assertIn(b"Friend One", response.data)

        # Verify db.get_all was called with the correct friend reference
        mock_db.get_all.assert_any_call([mock_friend_ref])


if __name__ == "__main__":
    unittest.main()
