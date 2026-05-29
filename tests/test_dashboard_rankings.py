from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.user.services.dashboard import get_dashboard_data


class TestDashboardRankings(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()
        self.user_id = "test_user"

    @patch("pickaladder.user.services.dashboard._fetch_vanity_stats")
    @patch("pickaladder.user.services.dashboard._fetch_social_and_tournaments")
    @patch("pickaladder.user.helpers.calculate_onboarding_progress")
    def test_get_dashboard_data_includes_rankings(
        self, mock_onboarding, mock_social, mock_vanity
    ) -> None:
        mock_vanity.return_value = ({}, {"total_games": 0})
        mock_social.return_value = {
            "friends": [],
            "requests": [],
            "group_rankings": [],
            "top_groups": [{"id": "g1", "name": "Top Group"}],
            "top_teams": [{"id": "t1", "name": "Top Team"}],
            "pending_tournament_invites": [],
            "active_tournaments": [],
            "past_tournaments": [],
        }
        mock_onboarding.return_value = 50

        result = get_dashboard_data(self.db, self.user_id)

        self.assertIn("top_groups", result)
        self.assertIn("top_teams", result)
        self.assertEqual(result["top_groups"][0]["name"], "Top Group")
        self.assertEqual(result["top_teams"][0]["name"], "Top Team")


if __name__ == "__main__":
    unittest.main()
