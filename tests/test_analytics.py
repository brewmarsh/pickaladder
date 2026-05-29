"""Tests for the analytics service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.season.analytics import AnalyticsService


class AnalyticsServiceTestCase(unittest.TestCase):
    """Test cases for the AnalyticsService."""

    def setUp(self) -> None:
        self.mock_db = MagicMock()

    @patch("pickaladder.season.analytics.SeasonRepository.get_all")
    def test_get_user_season_history(self, mock_get_all) -> None:
        """Test extracting user history from completed seasons."""
        # Setup: 2 completed seasons, 1 in-progress
        mock_get_all.return_value = [
            {
                "id": "s1",
                "name": "Season 1",
                "status": "COMPLETED",
                "endDate": "2026-01-01",
                "finalStandings": [
                    {"uid": "user1", "wins": 10, "point_diff": 50},
                    {"uid": "user2", "wins": 5, "point_diff": 0},
                ],
            },
            {
                "id": "s2",
                "name": "Season 2",
                "status": "COMPLETED",
                "endDate": "2026-04-01",
                "finalStandings": [
                    {"uid": "user2", "wins": 8, "point_diff": 20},
                    {"uid": "user1", "wins": 7, "point_diff": 10},
                ],
            },
            {
                "id": "s3",
                "name": "Active Season",
                "status": "ACTIVE",
                "endDate": "2026-07-01",
                "finalStandings": [],  # No snapshot yet
            },
        ]

        history = AnalyticsService.get_user_season_history(self.mock_db, "user1")

        assert len(history) == 2
        # Season 2 should be first (latest date)
        assert history[0]["seasonId"] == "s2"
        assert history[0]["rank"] == 2  # Ranked 2nd in S2
        assert history[0]["wins"] == 7

        # Season 1 should be second
        assert history[1]["seasonId"] == "s1"
        assert history[1]["rank"] == 1  # Ranked 1st in S1
        assert history[1]["wins"] == 10
        assert history[1]["pointDiff"] == 50

    @patch("pickaladder.season.analytics.SeasonRepository.get_all")
    def test_get_user_season_history_not_found(self, mock_get_all) -> None:
        """Test history for user not in any completed seasons."""
        mock_get_all.return_value = [
            {
                "id": "s1",
                "name": "Season 1",
                "status": "COMPLETED",
                "finalStandings": [{"uid": "other_user"}],
            },
        ]

        history = AnalyticsService.get_user_season_history(self.mock_db, "user1")
        assert len(history) == 0


if __name__ == "__main__":
    unittest.main()
