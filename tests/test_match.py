"""Tests for the match blueprint."""

from __future__ import annotations

import datetime
import unittest
from typing import cast
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
        self.mock_firestore_service.transactional.side_effect = lambda x: x

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.match.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_services": patch(
                "pickaladder.match.services.firestore", new=self.mock_firestore_service
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

    @patch("pickaladder.match.routes.MatchService.get_match_by_id")
    @patch("pickaladder.match.services.MatchService.get_candidate_player_ids")
    def test_record_match(
        self, mock_get_candidate_player_ids: MagicMock, mock_get_match: MagicMock
    ) -> None:
        """Test recording a new match."""

        def get_candidates_side_effect(
            db, user_id, group_id, tournament_id, include_user=False
        ):
            if include_user:
                return {user_id, MOCK_OPPONENT_ID}
            return {MOCK_OPPONENT_ID}

        mock_get_candidate_player_ids.side_effect = get_candidates_side_effect
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

        # Mock match data for summary page redirect
        mock_get_match.return_value = {
            "id": "match_123",
            "matchType": "singles",
            "player1Score": 11,
            "player2Score": 5,
            "player1Ref": MagicMock(id=MOCK_USER_ID),
            "player2Ref": MagicMock(id=MOCK_OPPONENT_ID),
            "matchDate": datetime.datetime.now(),
        }

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
        # Check that the match was saved (using either add or document().set())
        self.assertTrue(
            mock_matches_collection.add.called
            or mock_matches_collection.document.called
        )

    @patch("pickaladder.match.routes.MatchService.get_match_by_id")
    def test_view_match_summary(self, mock_get_match: MagicMock) -> None:
        """Test viewing the match summary page."""
        self._set_session_user()
        mock_match_id = "match_123"

        mock_get_match.return_value = {
            "id": mock_match_id,
            "matchType": "singles",
            "player1Score": 11,
            "player2Score": 5,
            "player1Ref": MagicMock(id=MOCK_USER_ID),
            "player2Ref": MagicMock(id=MOCK_OPPONENT_ID),
            "matchDate": datetime.datetime.now(),
        }

        # Mock participant fetching
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document.return_value
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        response = self.client.get(
            f"/match/summary/{mock_match_id}", headers=self._get_auth_headers()
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match Summary", response.data)
        self.assertIn(b"11", response.data)
        self.assertIn(b"5", response.data)
        user_name = cast(str, MOCK_USER_DATA["name"])
        self.assertIn(user_name.encode(), response.data)

    @patch("pickaladder.match.routes.MatchService.get_match_by_id")
    def test_view_match_summary_doubles(self, mock_get_match: MagicMock) -> None:
        """Test viewing the match summary page for a doubles match."""
        self._set_session_user()
        mock_match_id = "match_doubles"

        p1_ref = MagicMock(id=MOCK_USER_ID)
        p2_ref = MagicMock(id="partner_id")
        opp1_ref = MagicMock(id=MOCK_OPPONENT_ID)
        opp2_ref = MagicMock(id="opponent2_id")

        mock_get_match.return_value = {
            "id": mock_match_id,
            "matchType": "doubles",
            "player1Score": 11,
            "player2Score": 5,
            "team1": [p1_ref, p2_ref],
            "team2": [opp1_ref, opp2_ref],
            "matchDate": datetime.datetime.now(),
        }

        # Mock participant fetching
        mock_db = self.mock_firestore_service.client.return_value

        # Setup mock users
        user_doc = MagicMock()
        user_doc.exists = True
        user_doc.to_dict.return_value = {"name": "Some User"}
        mock_db.get_all.return_value = [user_doc, user_doc]

        response = self.client.get(
            f"/match/summary/{mock_match_id}", headers=self._get_auth_headers()
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match Summary", response.data)
        self.assertIn(b"11", response.data)
        self.assertIn(b"5", response.data)
        self.assertIn(b"Winners", response.data)
        self.assertIn(b"Losers", response.data)

    def test_record_match_rematch_param(self) -> None:
        """Test that player2 param pre-fills the form."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock necessary Firestore calls for page load
        mock_user_snapshot = MagicMock(exists=True)
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_db.collection("users").document(
            MOCK_USER_ID
        ).get.return_value = mock_user_snapshot

        # Mock get_candidate_player_ids
        with patch(
            "pickaladder.match.routes.MatchService.get_candidate_player_ids"
        ) as mock_get_candidates:
            mock_get_candidates.return_value = {MOCK_OPPONENT_ID}
            # Mock get_all for choices
            opp_doc = MagicMock(exists=True, id=MOCK_OPPONENT_ID)
            opp_doc.to_dict.return_value = MOCK_OPPONENT_DATA
            mock_db.get_all.return_value = [opp_doc]

            response = self.client.get(
                f"/match/record?player2={MOCK_OPPONENT_ID}",
                headers=self._get_auth_headers(),
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(MOCK_OPPONENT_ID.encode(), response.data)

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
