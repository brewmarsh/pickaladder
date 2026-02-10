"""Tests for TeamService."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from firebase_admin import firestore
from mockfirestore import MockFirestore

from pickaladder.teams.services import TeamService
from tests.conftest import patch_mockfirestore


class TestTeamService(unittest.TestCase):
    def setUp(self) -> None:
        patch_mockfirestore()
        self.db = MockFirestore()

        # Patch FieldPath in firestore module because it's missing in some environments
        if not hasattr(firestore, "FieldPath"):
            mock_field_path = MagicMock()
            mock_field_path.document_id.return_value = "__name__"
            firestore.FieldPath = mock_field_path

    def test_get_team_dashboard_data_success(self) -> None:
        # Create members
        user1_ref = self.db.collection("users").document("user1")
        user1_ref.set({"name": "Player 1", "email": "p1@example.com"})

        user2_ref = self.db.collection("users").document("user2")
        user2_ref.set({"name": "Player 2", "email": "p2@example.com"})

        # Create team
        team_id = "team123"
        team_ref = self.db.collection("teams").document(team_id)
        team_data = {
            "name": "Team A",
            "member_ids": ["user1", "user2"],
            "members": [user1_ref, user2_ref],
            "stats": {"wins": 10, "losses": 5, "elo": 1300},
        }
        team_ref.set(team_data)

        # Create opponent team
        opponent_team_id = "team456"
        opponent_team_ref = self.db.collection("teams").document(opponent_team_id)
        opponent_team_ref.set({"name": "Opponent Team"})

        # Create a match
        match_id = "match1"
        match_ref = self.db.collection("matches").document(match_id)
        match_ref.set(
            {
                "team1Id": team_id,
                "team2Id": opponent_team_id,
                "winner": "team1",
                "matchDate": firestore.SERVER_TIMESTAMP,
                "player1_score": 11,
                "player2_score": 5,
            }
        )

        data = TeamService.get_team_dashboard_data(self.db, team_id)

        self.assertIsNotNone(data)
        if data:
            self.assertEqual(data["team"]["name"], "Team A")
            self.assertEqual(len(data["members"]), 2)
            self.assertEqual(len(data["recent_matches"]), 1)
            self.assertEqual(
                data["recent_matches"][0]["opponent"]["id"], opponent_team_id
            )
            self.assertEqual(data["win_percentage"], (10 / 15) * 100)
            self.assertEqual(data["streak"], 1)
            self.assertEqual(data["streak_type"], "W")

    def test_get_team_dashboard_data_not_found(self) -> None:
        data = TeamService.get_team_dashboard_data(self.db, "nonexistent")
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
