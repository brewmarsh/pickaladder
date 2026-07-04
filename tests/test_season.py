"""Tests for the season service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.season.services import (
    SeasonFinalizationService,
    SeasonService,
    SeasonStandingsService,
)


class SeasonServiceTestCase(unittest.TestCase):
    """Test cases for the SeasonService."""

    def setUp(self) -> None:
        self.mock_db = MagicMock()

    @patch("pickaladder.season.services.SeasonRepository")
    def test_create_season(self, mock_repo) -> None:
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
        assert season_id == "season1"
        mock_repo.create.assert_called_once_with(self.mock_db, data)

    @patch("pickaladder.group.services.group_service.GroupService.get_group_details")
    @patch("pickaladder.season.services.SeasonRepository")
    def test_calculate_standings(self, mock_repo, mock_group_service) -> None:
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
                "seasonId": "s1",
            },
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Ref": p1_ref,
                "player2Ref": p2_ref,
                "player1Score": 11,
                "player2Score": 9,
                "seasonId": "s1",
            },
        ]
        mock_repo.get_season_matches.return_value = matches
        mock_repo.get_by_id.return_value = {"id": "s1", "groupId": "g1"}

        # Mock group service to return participant ids
        mock_group_service.return_value = {
            "participants": [
                {"user": {"id": "p1", "username": "Player 1"}},
                {"user": {"id": "p2", "username": "Player 2"}},
            ],
        }

        standings = SeasonStandingsService.get_season_standings(self.mock_db, "s1")

        assert len(standings) == 2
        # p1 should be first
        assert standings[0]["uid"] == "p1"
        assert standings[0]["wins"] == 2
        assert standings[0]["point_diff"] == 8  # (11-5) + (11-9) = 6 + 2 = 8

        # p2 should be second
        assert standings[1]["uid"] == "p2"
        assert standings[1]["losses"] == 2
        assert standings[1]["point_diff"] == -8

    @patch("pickaladder.season.services.SeasonStandingsService.get_season_standings")
    @patch("pickaladder.season.services.SeasonRepository")
    def test_calculate_movements(self, mock_repo, mock_standings) -> None:
        """Test promotion and relegation logic."""
        # Setup: P1 (1st), P2 (2nd), P3 (3rd), P4 (4th)
        # Rules: Top 1 promote, Bottom 1 relegate
        mock_repo.get_by_id.return_value = {
            "id": "s1",
            "movementRules": {"promotionCount": 1, "relegationCount": 1},
        }
        mock_standings.return_value = [
            {"uid": "p1", "wins": 3},
            {"uid": "p2", "wins": 2},
            {"uid": "p3", "wins": 1},
            {"uid": "p4", "wins": 0},
        ]

        movements = SeasonFinalizationService.calculate_movements(self.mock_db, "s1")

        assert len(movements["promoted"]) == 1
        assert movements["promoted"][0]["uid"] == "p1"

        assert len(movements["relegated"]) == 1
        assert movements["relegated"][0]["uid"] == "p4"

        assert len(movements["retained"]) == 2
        assert movements["retained"][0]["uid"] == "p2"
        assert movements["retained"][1]["uid"] == "p3"

    @patch("pickaladder.season.services.SeasonFinalizationService.calculate_movements")
    @patch("pickaladder.season.services.SeasonRepository")
    def test_apply_movements(self, mock_repo, mock_calc) -> None:
        """Test the transition suggestion engine."""
        mock_repo.get_by_id.return_value = {"id": "old_s"}
        mock_calc.return_value = {
            "promoted": [{"uid": "p1"}],
            "relegated": [{"uid": "p4"}],
            "retained": [{"uid": "p2"}, {"uid": "p3"}],
        }

        result = SeasonFinalizationService.apply_movements(self.mock_db, "old_s")

        assert "p1" in result["suggested_participants"]  # type: ignore
        assert "p2" in result["suggested_participants"]  # type: ignore
        assert "p3" in result["suggested_participants"]  # type: ignore
        assert "p4" in result["relegated_participants"]  # type: ignore
        assert len(result["suggested_participants"]) == 3  # type: ignore


if __name__ == "__main__":
    unittest.main()
