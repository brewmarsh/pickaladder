"""Tests for the match blueprint."""

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

    def setUp(self):
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
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self):
        return {"Authorization": "Bearer mock-token"}

    def test_create_match(self):
        """Test creating a new match."""
        self._set_session_user()

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")

        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_opponent_doc = mock_users_collection.document(MOCK_OPPONENT_ID)
        mock_opponent_snapshot = MagicMock()
        mock_opponent_snapshot.exists = True
        mock_opponent_snapshot.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_doc.get.return_value = mock_opponent_snapshot

        mock_matches_collection = mock_db.collection("matches")

        mock_friends_collection = (
            mock_db.collection("users").document(MOCK_USER_ID).collection("friends")
        )
        mock_friend_doc = MagicMock()
        mock_friend_doc.id = MOCK_OPPONENT_ID
        mock_friend_doc.to_dict.return_value = {"status": "accepted"}
        mock_friends_collection.stream.return_value = [mock_friend_doc]

        mock_opponent_user_query = mock_db.collection("users").where.return_value
        mock_opponent_user_doc = MagicMock()
        mock_opponent_user_doc.id = MOCK_OPPONENT_ID
        mock_opponent_user_doc.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_user_query.stream.return_value = [mock_opponent_user_doc]

        response = self.client.post(
            "/match/create",
            headers=self._get_auth_headers(),
            data={
                "player2": MOCK_OPPONENT_ID,
                "player1_score": 11,
                "player2_score": 5,
                "match_date": datetime.date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match created successfully.", response.data)
        mock_matches_collection.add.assert_called_once()

    def test_pending_invites_query_uses_correct_field(self):
        """Test that pending invites are queried using 'inviter_id'."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Grab the default collection mock (which serves as users collection for now)
        mock_users_col = mock_db.collection("users")

        # Configure user fetch on this mock
        mock_user_doc = mock_users_col.document(MOCK_USER_ID)
        mock_user_doc.get.return_value.to_dict.return_value = {}  # g.user will get uid added automatically

        # Also configure friends on this mock (since friends query uses db.collection("users").document(...))
        mock_user_doc.collection("friends").stream.return_value = []

        mock_group_invites_col = MagicMock()
        mock_invite_doc = MagicMock()
        mock_invite_doc.to_dict.return_value = {"email": "pending@example.com"}

        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_group_invites_col.where.return_value = mock_query1
        mock_query1.where.return_value = mock_query2
        mock_query2.stream.return_value = [mock_invite_doc]

        def collection_side_effect(name):
            if name == "group_invites":
                return mock_group_invites_col
            if name == "users":
                return mock_users_col
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        self.client.get("/match/create", headers=self._get_auth_headers())

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

    def test_candidates_mixed_status(self):
        """Test that both accepted and pending invites are included in the opponent list."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mocks
        mock_users_col = MagicMock()
        mock_group_invites_col = MagicMock()

        def collection_side_effect(name):
            if name == "users":
                return mock_users_col
            if name == "group_invites":
                return mock_group_invites_col
            return MagicMock()

        mock_db.collection.side_effect = collection_side_effect

        # User setup
        mock_user_doc = mock_users_col.document(MOCK_USER_ID)
        mock_user_doc.get.return_value.to_dict.return_value = {}
        # No friends
        mock_user_doc.collection.return_value.stream.return_value = []

        # Invites setup
        # 1. Accepted Invite: used=True, has used_by
        invite_accepted = MagicMock()
        invite_accepted.to_dict.return_value = {
            "email": "ignored_in_favor_of_id@example.com",
            "used": True,
            "used_by": "user_accepted_id",
        }

        # 2. Pending Invite: used=False (or missing), has email
        invite_pending = MagicMock()
        invite_pending.to_dict.return_value = {
            "email": "pending@example.com",
            "used": False,
        }

        # Query result for invites
        mock_query_invites = MagicMock()
        mock_group_invites_col.where.return_value = mock_query_invites
        mock_query_invites.stream.return_value = [invite_accepted, invite_pending]

        # Users Lookup Setup
        # We need to ensure users are returned.
        # 1. User from 'pending' email
        user_pending = MagicMock()
        user_pending.id = "user_pending_id"
        user_pending.to_dict.return_value = {"name": "User Pending"}

        # 2. User from 'accepted' ID
        user_accepted = MagicMock()
        user_accepted.id = "user_accepted_id"
        user_accepted.to_dict.return_value = {"name": "User Accepted"}

        # The code does two things:
        # A. Look up users by email (for pending).
        # B. Look up users by ID (for collected IDs: from used_by AND from email lookup).

        # Mock the email lookup
        mock_query_users_by_email = MagicMock()
        mock_users_col.where.return_value = mock_query_users_by_email

        def stream_side_effect():
            # This is complex because 'stream' is called on the result of 'where'.
            # We need to distinguish between the 'email' query and the '__name__' query if possible,
            # or just return everything that matches logically.

            # Inspect the last call to 'where' on the collection mock
            # Note: The code calls db.collection("users").where(...).stream()
            # Since we return the SAME mock_query_users_by_email for all .where calls,
            # we can inspect its parent's call args.

            # However, side_effect on stream() doesn't give us access to the query params easily.
            # A better approach is to use side_effect on .where() to return DIFFERENT query mocks.
            pass

        # Better Mocking Strategy for .where()
        def where_side_effect(filter=None):
            query_mock = MagicMock()
            if filter:
                if filter.field_path == "email" and filter.op_string == "in":
                    # Pending user email lookup
                    if "pending@example.com" in filter.value:
                        query_mock.stream.return_value = [user_pending]
                    else:
                        query_mock.stream.return_value = []
                elif filter.field_path == "__name__" and filter.op_string == "in":
                    # Final ID lookup
                    # We expect both user_pending_id and user_accepted_id to be in the list
                    # But the 'in' operator value is a list of DocumentReferences.
                    # We can check the IDs of these refs.
                    requested_ids = [ref.id for ref in filter.value]
                    results = []
                    if "user_pending_id" in requested_ids:
                        results.append(user_pending)
                    if "user_accepted_id" in requested_ids:
                        results.append(user_accepted)
                    query_mock.stream.return_value = results
                else:
                    query_mock.stream.return_value = []
            return query_mock

        mock_users_col.where.side_effect = where_side_effect

        # Also need to make sure db.collection("users").document(uid) returns a ref with the correct ID
        def document_side_effect(doc_id):
            doc_ref = MagicMock()
            doc_ref.id = doc_id
            return doc_ref

        mock_users_col.document.side_effect = document_side_effect

        response = self.client.get("/match/create", headers=self._get_auth_headers())
        self.assertEqual(response.status_code, 200)
        html = response.data.decode()

        # Check if both users are present in the options
        self.assertIn('value="user_accepted_id"', html)
        self.assertIn("User Accepted", html)

        self.assertIn('value="user_pending_id"', html)
        self.assertIn("User Pending", html)


if __name__ == "__main__":
    unittest.main()
