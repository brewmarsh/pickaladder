from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pickaladder.stats.services import PredictionService


@pytest.fixture
def db():
    return MagicMock()


def test_prediction_basic(db):
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

        prediction = PredictionService.predict_matchup(db, ["u1"], ["u2"])

        assert prediction["team1_prob"] == 50
        assert prediction["team2_prob"] == 50
        assert prediction["insight"] == "A closely matched game."


def test_prediction_with_h2h(db):
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

        prediction = PredictionService.predict_matchup(db, ["u1"], ["u2"])

        assert prediction["team1_prob"] > 50
        # Since u1 form is 100
        assert prediction["insight"] == "Team is on a hot streak!"
