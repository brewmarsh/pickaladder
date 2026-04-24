"""Tests for the season service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.season.services import SeasonService, SeasonStandingsService


class SeasonServiceTestCase(unittest.TestCase):
    """Test cases for the SeasonService."""

    def setUp(self):
        self.mock_db = MagicMock()

    @patch("pickaladder.season.services.SeasonRepository")
    def test_create_season(self, mock_repo):
        """Test creating a season."""
        data = {
            "name": "Spring 2026",
            "groupId": "group1",
            "startDate": "2026-04-01",
            "endDate": "2026-06-30",
            "status": "DRAFT",
        }

        mock_repo.create.return_value = "season1"

        season_id = SeasonService.create_season(self.mock_db, data)
        self.assertEqual(season_id, "season1")
        mock_repo.create.assert_called_once_with(self.mock_db, data)

    @patch("pickaladder.group.services.group_service.GroupService.get_group_details")
    @patch("pickaladder.season.services.SeasonRepository")
    def test_calculate_standings(self, mock_repo, mock_group_service):
        """Test calculating standings from matches."""
        # 2 matches:
        # Match 1: p1 beats p2 11-5
        # Match 2: p1 beats p2 11-9

        p1_ref = MagicMock()
        p1_ref.id = "p1"
        p2_ref = MagicMock()
        p2_ref.id = "p2"

        matches = [
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Ref": p1_ref,
                "player2Ref": p2_ref,
                "player1Score": 11,
                "player2Score": 5,
                "seasonId": "s1"
            },
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Ref": p1_ref,
                "player2Ref": p2_ref,
                "player1Score": 11,
                "player2Score": 9,
                "seasonId": "s1"
            }
        ]
        mock_repo.get_season_matches.return_value = matches
        mock_repo.get_by_id.return_value = {"id": "s1", "groupId": "g1"}

        # Mock group service to return participant ids
        mock_group_service.return_value = {
            "participants": [
                {"user": {"id": "p1", "username": "Player 1"}},
                {"user": {"id": "p2", "username": "Player 2"}}
            ]
        }

        standings = SeasonStandingsService.get_season_standings(self.mock_db, "s1")

        self.assertEqual(len(standings), 2)
        # p1 should be first
        self.assertEqual(standings[0]["uid"], "p1")
        self.assertEqual(standings[0]["wins"], 2)
        self.assertEqual(standings[0]["point_diff"], 8) # (11-5) + (11-9) = 6 + 2 = 8

        # p2 should be second
        self.assertEqual(standings[1]["uid"], "p2")
        self.assertEqual(standings[1]["losses"], 2)
        self.assertEqual(standings[1]["point_diff"], -8)

if __name__ == "__main__":
    unittest.main()
