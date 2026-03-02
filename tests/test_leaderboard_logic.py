"""Tests for the global leaderboard filtering logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.match.services import MatchService


class TestLeaderboardLogic(unittest.TestCase):
    """Test case for the global leaderboard filtering logic."""

    @patch("pickaladder.match.services.firestore")
    def test_get_leaderboard_data_filters_inactive(
        self, mock_firestore: MagicMock
    ) -> None:
        """Test that players with zero games are filtered out using cached stats."""
        # Mock Firestore client
        mock_db = MagicMock()

        # Mock users with cached stats
        user1 = MagicMock()
        user1.id = "u1"
        user1.to_dict.return_value = {
            "name": "User 1",
            "stats": {"wins": 4, "losses": 2},
        }

        user2 = MagicMock()
        user2.id = "u2"
        user2.to_dict.return_value = {
            "name": "User 2",
            "stats": {"wins": 2, "losses": 2},
        }

        user3 = MagicMock()
        user3.id = "u3"
        user3.to_dict.return_value = {
            "name": "User 3",
            "stats": {"wins": 0, "losses": 0},
        }

        mock_db.collection.return_value.stream.return_value = [
            user1,
            user2,
            user3,
        ]

        # Running the function
        players = MatchService.get_leaderboard_data(mock_db)

        # Assertions
        # User 1 and User 2 have > 0 games
        self.assertEqual(len(players), 2)
        self.assertEqual(players[0]["id"], "u1")
        self.assertEqual(players[0]["games_played"], 6)
        self.assertEqual(players[1]["id"], "u2")
        self.assertEqual(players[1]["games_played"], 4)


if __name__ == "__main__":
    unittest.main()
