"""Tests for the global leaderboard filtering logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.match.services import MatchService


class TestLeaderboardLogic(unittest.TestCase):
    """Test case for the global leaderboard filtering logic."""

    @patch("pickaladder.match.services.firestore")
    @patch("pickaladder.match.services.MatchService.get_player_record")
    def test_get_leaderboard_data_filters_inactive(
        self, mock_get_player_record: MagicMock, mock_firestore: MagicMock
    ) -> None:
        """Test that players with fewer than 5 games are filtered out."""
        # Mock Firestore client
        mock_db = MagicMock()

        def document_side_effect(uid: str) -> MagicMock:
            """Ensure document(uid).id returns uid."""
            doc = MagicMock()
            doc.id = uid
            return doc

        mock_db.collection.return_value.document.side_effect = document_side_effect

        # Mock users
        user1 = MagicMock()
        user1.id = "u1"
        user1.to_dict.return_value = {"name": "User 1"}

        user2 = MagicMock()
        user2.id = "u2"
        user2.to_dict.return_value = {"name": "User 2"}

        user3 = MagicMock()
        user3.id = "u3"
        user3.to_dict.return_value = {"name": "User 3"}

        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            user1,
            user2,
            user3,
        ]

        # u1: 6 games (should stay)
        # u2: 4 games (should be filtered)
        # u3: 0 games (should be filtered)
        def get_record_side_effect(
            db: MagicMock, user_ref: MagicMock
        ) -> dict[str, int]:
            """Side effect to return different records for different users."""
            if user_ref.id == "u1":
                return {"wins": 4, "losses": 2}
            if user_ref.id == "u2":
                return {"wins": 2, "losses": 2}
            if user_ref.id == "u3":
                return {"wins": 0, "losses": 0}
            return {"wins": 0, "losses": 0}

        mock_get_player_record.side_effect = get_record_side_effect

        # Running the function
        players = MatchService.get_leaderboard_data(mock_db)

        # Assertions
        # Only User 1 has >= 5 games
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["id"], "u1")
        self.assertEqual(players[0]["games_played"], 6)


if __name__ == "__main__":
    unittest.main()
