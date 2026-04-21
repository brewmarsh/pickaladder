"""Tests for session-based match recording."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from firebase_admin import firestore
from pickaladder import create_app

MOCK_USER_ID = "winner_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "winner@example.com"}
MOCK_USER_DATA = {"name": "Winner", "isAdmin": False}

MOCK_OPPONENT_ID = "loser_uid"
MOCK_OPPONENT_PAYLOAD = {"uid": MOCK_OPPONENT_ID, "email": "loser@example.com"}
MOCK_OPPONENT_DATA = {"name": "Loser", "isAdmin": False}

MOCK_SESSION_ID = "test_session_123"
MOCK_SESSION_DATA = {
    "id": MOCK_SESSION_ID,
    "groupId": "group_abc",
    "playerIds": [MOCK_USER_ID, MOCK_OPPONENT_ID],
    "matchTypeDefault": "singles",
}

class SessionMatchRecordingTestCase(unittest.TestCase):
    """Test case for recording matches within a session."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()
        self.mock_firestore_service.FieldFilter = firestore.FieldFilter
        self.mock_firestore_service.transactional.side_effect = lambda x: x
        self.mock_db = self.mock_firestore_service.client.return_value

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_match_routes": patch("pickaladder.match.routes.firestore", new=self.mock_firestore_service),
            "firestore_auth_routes": patch("pickaladder.auth.routes.firestore", new=self.mock_firestore_service),
            "firestore_candidate": patch("pickaladder.match.services.candidate_service.firestore", new=self.mock_firestore_service),
            "firestore_admin": patch("firebase_admin.firestore", new=self.mock_firestore_service),
            "firestore_app": patch("pickaladder.firestore", new=self.mock_firestore_service),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
            "FIREBASE_API_KEY": "dummy-test-key",
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD
        
        # Mock for auth before_request load_user_document
        mock_user_snap = MagicMock()
        mock_user_snap.exists = True
        mock_user_snap.to_dict.return_value = MOCK_USER_DATA
        self.mock_db.collection("users").document(MOCK_USER_ID).get.return_value = mock_user_snap

    def _get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer mock-token"}

    @patch("pickaladder.match.routes.MatchCommandService.record_match")
    def test_record_match_with_session_id(self, mock_record_match: MagicMock) -> None:
        """Test that recording a match with session_id redirects to quick log."""
        self._set_session_user()
        
        # Mock session doc for choices population
        mock_session_snap = MagicMock()
        mock_session_snap.exists = True
        mock_session_snap.to_dict.return_value = MOCK_SESSION_DATA
        self.mock_db.collection("sessions").document(MOCK_SESSION_ID).get.return_value = mock_session_snap
        
        # Mock users for SelectField choices (MatchQueryService.get_player_names equivalent)
        mock_user_snap = MagicMock(exists=True, id=MOCK_USER_ID)
        mock_user_snap.to_dict.return_value = MOCK_USER_DATA
        mock_opp_snap = MagicMock(exists=True, id=MOCK_OPPONENT_ID)
        mock_opp_snap.to_dict.return_value = MOCK_OPPONENT_DATA
        self.mock_db.get_all.return_value = [mock_user_snap, mock_opp_snap]

        # Mock successful recording result
        mock_result = MagicMock()
        mock_result.id = "new_match_id"
        mock_record_match.return_value = mock_result

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
                "session_id": MOCK_SESSION_ID
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        # Verify redirect to quick log
        self.assertIn(f"/group/session/{MOCK_SESSION_ID}/quick-log", response.location)
        
        # Verify session_id was passed to MatchCommandService.record_match via submission
        submission = mock_record_match.call_args[0][1]
        self.assertEqual(submission.session_id, MOCK_SESSION_ID)

    def test_candidate_players_limited_to_session(self) -> None:
        """Test that candidate players are limited to session pool when session_id is provided."""
        from pickaladder.match.services.candidate_service import MatchCandidateService
        
        # Mock session doc with specific players
        SESSION_PLAYERS = ["p1", "p2", "p3"]
        mock_session_snap = MagicMock()
        mock_session_snap.exists = True
        mock_session_snap.to_dict.return_value = {"playerIds": SESSION_PLAYERS}
        self.mock_db.collection("sessions").document(MOCK_SESSION_ID).get.return_value = mock_session_snap
        
        candidates = MatchCandidateService.get_candidate_player_ids(
            self.mock_db, "p1", session_id=MOCK_SESSION_ID, include_user=True
        )
        
        self.assertEqual(candidates, set(SESSION_PLAYERS))

if __name__ == "__main__":
    unittest.main()
