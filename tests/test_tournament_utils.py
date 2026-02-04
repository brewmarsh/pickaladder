"""Tests for tournament utility functions."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.tournament.utils import (
    aggregate_match_data,
    sort_and_format_standings,
)


class TournamentUtilsTestCase(unittest.TestCase):
    """Test case for tournament utility functions."""

    def test_aggregate_match_data_singles(self) -> None:
        """Test aggregation for singles matches."""
        # Mock matches
        match1 = MagicMock()
        match1.to_dict.return_value = {
            "player1Ref": MagicMock(id="p1"),
            "player2Ref": MagicMock(id="p2"),
            "player1Score": 11,
            "player2Score": 5,
        }
        match2 = MagicMock()
        match2.to_dict.return_value = {
            "player1Ref": MagicMock(id="p1"),
            "player2Ref": MagicMock(id="p2"),
            "player1Score": 8,
            "player2Score": 11,
        }

        matches = [match1, match2]
        raw_standings = aggregate_match_data(matches, "singles")

        self.assertEqual(raw_standings["p1"]["wins"], 1)
        self.assertEqual(raw_standings["p1"]["losses"], 1)
        self.assertEqual(raw_standings["p1"]["point_diff"], 11 - 5 + 8 - 11)  # 6 - 3 = 3

        self.assertEqual(raw_standings["p2"]["wins"], 1)
        self.assertEqual(raw_standings["p2"]["losses"], 1)
        self.assertEqual(raw_standings["p2"]["point_diff"], 5 - 11 + 11 - 8)  # -6 + 3 = -3

    def test_aggregate_match_data_doubles(self) -> None:
        """Test aggregation for doubles matches."""
        match1 = MagicMock()
        match1.to_dict.return_value = {
            "team1Id": "t1",
            "team2Id": "t2",
            "player1Score": 21,
            "player2Score": 15,
        }
        matches = [match1]
        raw_standings = aggregate_match_data(matches, "doubles")

        self.assertEqual(raw_standings["t1"]["wins"], 1)
        self.assertEqual(raw_standings["t1"]["point_diff"], 6)
        self.assertEqual(raw_standings["t2"]["losses"], 1)
        self.assertEqual(raw_standings["t2"]["point_diff"], -6)

    def test_sort_and_format_standings(self) -> None:
        """Test sorting and formatting of standings."""
        db = MagicMock()
        raw_standings = {
            "p1": {"id": "p1", "wins": 1, "losses": 1, "point_diff": 10},
            "p2": {"id": "p2", "wins": 1, "losses": 1, "point_diff": 5},
            "p3": {"id": "p3", "wins": 2, "losses": 0, "point_diff": 20},
        }

        # Mock user fetching
        mock_p1 = MagicMock()
        mock_p1.exists = True
        mock_p1.id = "p1"
        mock_p1.to_dict.return_value = {"username": "User1"}

        mock_p2 = MagicMock()
        mock_p2.exists = True
        mock_p2.id = "p2"
        mock_p2.to_dict.return_value = {"username": "User2"}

        mock_p3 = MagicMock()
        mock_p3.exists = True
        mock_p3.id = "p3"
        mock_p3.to_dict.return_value = {"username": "User3"}

        db.get_all.return_value = [mock_p1, mock_p2, mock_p3]

        sorted_standings = sort_and_format_standings(db, raw_standings, "singles")

        # p3 should be first (2 wins)
        self.assertEqual(sorted_standings[0]["id"], "p3")
        self.assertEqual(sorted_standings[0]["name"], "User3")

        # p1 should be second (1 win, 1 loss, 10 point_diff)
        self.assertEqual(sorted_standings[1]["id"], "p1")
        self.assertEqual(sorted_standings[1]["point_diff"], 10)

        # p2 should be third (1 win, 1 loss, 5 point_diff)
        self.assertEqual(sorted_standings[2]["id"], "p2")
        self.assertEqual(sorted_standings[2]["point_diff"], 5)

if __name__ == "__main__":
    unittest.main()
