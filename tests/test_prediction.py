from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.stats.services import PredictionService

# Constants for test values to avoid magic number linting issues
DEFAULT_PROB = 50
HOT_STREAK_INSIGHT = "Team is on a hot streak!"
CLOSELY_MATCHED_INSIGHT = "A closely matched game."


class TestPredictionService(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()

    def test_prediction_basic(self) -> None:
        # Mock UserService methods
        with patch("pickaladder.stats.services.UserService") as mock_user_service:
            mock_user_service.get_h2h_stats.return_value = None
            mock_user_service.get_user_matches.return_value = []
            mock_user_service.calculate_stats.return_value = {
                "wins": 0,
                "losses": 0,
                "total_games": 0,
                "win_rate": 0,
                "processed_matches": [],
            }

            prediction = PredictionService.predict_matchup(self.db, ["u1"], ["u2"])

            self.assertEqual(prediction["team1_prob"], DEFAULT_PROB)
            self.assertEqual(prediction["team2_prob"], DEFAULT_PROB)
            self.assertEqual(prediction["insight"], CLOSELY_MATCHED_INSIGHT)

    def test_prediction_with_h2h(self) -> None:
        with patch("pickaladder.stats.services.UserService") as mock_user_service:
            # u1 won against u2
            mock_user_service.get_h2h_stats.return_value = {"wins": 1, "losses": 0}

            # Team 1 form (u1)
            # We need to handle multiple calls to get_user_matches and calculate_stats
            def side_effect_matches(db, uid):
                return [MagicMock()]

            mock_user_service.get_user_matches.side_effect = side_effect_matches

            def side_effect_stats(matches, uid):
                if uid == "u1":
                    return {
                        "win_rate": 100,
                        "total_games": 1,
                        "processed_matches": [{"user_won": True}],
                    }
                else:
                    return {
                        "win_rate": 0,
                        "total_games": 1,
                        "processed_matches": [{"user_won": False}],
                    }

            mock_user_service.calculate_stats.side_effect = side_effect_stats

            prediction = PredictionService.predict_matchup(self.db, ["u1"], ["u2"])

            self.assertGreater(prediction["team1_prob"], DEFAULT_PROB)
            # Since u1 form is 100
            self.assertEqual(prediction["insight"], HOT_STREAK_INSIGHT)


if __name__ == "__main__":
    unittest.main()
