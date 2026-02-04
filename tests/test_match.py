"""Tests for the match blueprint."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from firebase_admin import firestore

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "winner_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "winner@example.com"}
MOCK_USER_DATA = {"name": "Winner", "isAdmin": False}

MOCK_OPPONENT_ID = "loser_uid"
MOCK_OPPONENT_PAYLOAD = {"uid": MOCK_OPPONENT_ID, "email": "loser@example.com"}
MOCK_OPPONENT_DATA = {"name": "Loser", "isAdmin": False}


class MatchRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the match blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()
        # Ensure FieldFilter is available for inspection in tests
        self.mock_firestore_service.FieldFilter = firestore.FieldFilter

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.match.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "user_firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost",
                "FIREBASE_API_KEY": "dummy-test-key",
            }
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

    def test_record_match_page_load(self) -> None:
        """Test that the record match page loads correctly."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_friends_collection = mock_user_doc.collection("friends")
        mock_friends_collection.stream.return_value = []

        mock_group_invites_col = MagicMock()
        (
            mock_group_invites_col.where.return_value.where.return_value.stream.return_value
        ) = []

        def collection_side_effect(name: str) -> MagicMock:
            """Firestore collection side effect mock."""
            if name == "group_invites":
                return mock_group_invites_col
            if name == "users":
                return mock_users_collection
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        response = self.client.get("/match/record", headers=self._get_auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'apiKey: "dummy-test-key"', response.data)

    @patch("pickaladder.match.routes._get_candidate_player_ids")
    def test_record_match(self, mock_get_candidate_player_ids: MagicMock) -> None:
        """Test recording a new match."""
        mock_get_candidate_player_ids.return_value = {MOCK_OPPONENT_ID}
        self._set_session_user()

        mock_db = self.mock_firestore_service.client.return_value

        # Mock the db.get_all call that populates the form choices
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.id = MOCK_USER_ID
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA

        mock_opponent_snapshot = MagicMock()
        mock_opponent_snapshot.exists = True
        mock_opponent_snapshot.id = MOCK_OPPONENT_ID
        mock_opponent_snapshot.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_db.get_all.return_value = [mock_user_snapshot, mock_opponent_snapshot]

        mock_matches_collection = mock_db.collection("matches")

        response = self.client.post(
            "/match/record",
            headers=self._get_auth_headers(),
            data={
                "player1": MOCK_USER_ID,
                "player2": MOCK_OPPONENT_ID,
                "player1_score": 11,
                "player2_score": 5,
                "match_date": datetime.date.today().isoformat(),
                "match_type": "singles",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match recorded successfully.", response.data)
        mock_matches_collection.add.assert_called_once()

    def test_pending_invites_query_uses_correct_field(self) -> None:
        """Test that pending invites are queried using 'inviter_id'."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Grab the default collection mock (which serves as users collection for now)
        mock_users_col = mock_db.collection("users")

        # Configure user fetch on this mock
        mock_user_doc = mock_users_col.document(MOCK_USER_ID)
        # g.user will get uid added automatically
        mock_user_doc.get.return_value.to_dict.return_value = {}

        # Also configure friends on this mock (since friends query uses
        # db.collection("users").document(...))
        mock_user_doc.collection("friends").stream.return_value = []

        mock_group_invites_col = MagicMock()
        mock_invite_doc = MagicMock()
        mock_invite_doc.to_dict.return_value = {"email": "pending@example.com"}

        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_group_invites_col.where.return_value = mock_query1
        mock_query1.where.return_value = mock_query2
        mock_query2.stream.return_value = [mock_invite_doc]

        def collection_side_effect(name: str) -> MagicMock:
            """Firestore collection side effect mock."""
            if name == "group_invites":
                return mock_group_invites_col
            if name == "users":
                return mock_users_col
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        self.client.get("/match/record", headers=self._get_auth_headers())

        # Verify that we queried for 'inviter_id' (not 'invited_by')
        calls = []
        if mock_group_invites_col.where.call_args:
            calls.append(mock_group_invites_col.where.call_args)
        if mock_query1.where.call_args:
            calls.append(mock_query1.where.call_args)

        found_inviter_query = False
        for call in calls:
            if "filter" in call.kwargs:
                f = call.kwargs["filter"]
                if (
                    hasattr(f, "field_path")
                    and f.field_path == "inviter_id"
                    and f.op_string == "=="
                    and f.value == MOCK_USER_ID
                ):
                    found_inviter_query = True
                    break

        self.assertTrue(
            found_inviter_query,
            "Did not find query filtering by 'inviter_id' == user_id",
        )


if __name__ == "__main__":
    unittest.main()
