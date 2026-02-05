"""Tests for Tournament Match Integration."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from firebase_admin import firestore

from pickaladder import create_app
from pickaladder.match.routes import _get_candidate_player_ids
from pickaladder.user.services import UserService

# Mock data
MOCK_USER_ID = "user123"
MOCK_TOURNAMENT_ID = "tourney456"
MOCK_TOURNAMENT_DATA = {
    "name": "Summer Slam",
    "participant_ids": [MOCK_USER_ID, "opponent789"],
}


class TournamentMatchIntegrationTestCase(unittest.TestCase):
    """Test case for tournament match integration."""

    def setUp(self) -> None:
        """Set up a test client and mock environment."""
        self.mock_firestore_service = MagicMock()
        self.mock_firestore_service.FieldFilter = firestore.FieldFilter

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_match": patch(
                "pickaladder.match.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_user_utils": patch(
                "pickaladder.user.services.firestore", new=self.mock_firestore_service
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

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        """Set a mock user in the session."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
        self.mocks["verify_id_token"].return_value = {
            "uid": MOCK_USER_ID,
            "email": "user@example.com",
        }

    def test_candidate_players_restricted_to_tournament(self) -> None:
        """Test that candidate players are restricted to tournament participants."""
        mock_db = self.mock_firestore_service.client.return_value
        mock_tourney_doc = mock_db.collection("tournaments").document(
            MOCK_TOURNAMENT_ID
        )
        mock_tourney_snapshot = MagicMock()
        mock_tourney_snapshot.exists = True
        mock_tourney_snapshot.to_dict.return_value = MOCK_TOURNAMENT_DATA
        mock_tourney_doc.get.return_value = mock_tourney_snapshot

        candidates = _get_candidate_player_ids(
            MOCK_USER_ID, tournament_id=MOCK_TOURNAMENT_ID
        )

        self.assertEqual(candidates, {"opponent789"})
        # Should NOT include friends or other users
        mock_db.collection("users").document(MOCK_USER_ID).collection(
            "friends"
        ).stream.assert_not_called()

    def test_format_matches_for_dashboard_includes_tournament(self) -> None:
        """Test that format_matches_for_dashboard includes tournament names."""
        mock_db = self.mock_firestore_service.client.return_value

        # Mock match doc
        mock_match_doc = MagicMock()
        mock_match_doc.id = "match_abc"
        mock_match_data = {
            "player1Score": 11,
            "player2Score": 5,
            "player1Ref": MagicMock(id=MOCK_USER_ID),
            "player2Ref": MagicMock(id="opponent789"),
            "tournamentId": MOCK_TOURNAMENT_ID,
            "matchType": "singles",
        }
        mock_match_doc.to_dict.return_value = mock_match_data

        # Mock tournament doc
        mock_tourney_doc = MagicMock()
        mock_tourney_doc.exists = True
        mock_tourney_doc.id = MOCK_TOURNAMENT_ID
        mock_tourney_doc.to_dict.return_value = MOCK_TOURNAMENT_DATA

        mock_db.get_all.side_effect = [
            [
                MagicMock(
                    exists=True, id=MOCK_USER_ID, to_dict=lambda: {"username": "User1"}
                ),
                MagicMock(
                    exists=True,
                    id="opponent789",
                    to_dict=lambda: {"username": "User2"},
                ),
            ],  # Users
            [mock_tourney_doc],  # Tournaments
        ]

        formatted = UserService.format_matches_for_dashboard(
            mock_db, [mock_match_doc], MOCK_USER_ID
        )

        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["tournament_name"], "Summer Slam")


if __name__ == "__main__":
    unittest.main()
