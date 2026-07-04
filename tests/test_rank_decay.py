"""Tests for rank decay logic."""

from datetime import datetime, timedelta, timezone

from pickaladder.match.services.record_service import MatchRecordService


def test_calculate_rank_decay_active_user() -> None:
    """Active users (played within 30 days) should have 0 decay."""
    last_match = datetime.now(timezone.utc) - timedelta(days=10)
    user_data = {"last_match_date": last_match}
    decay = MatchRecordService.calculate_rank_decay(user_data)
    assert decay == 0


def test_calculate_rank_decay_inactive_user() -> None:
    """Inactive users should have positive decay."""
    # 40 days inactive -> (40-30) * decay_per_day
    last_match = datetime.now(timezone.utc) - timedelta(days=40)
    user_data = {"last_match_date": last_match}
    decay = MatchRecordService.calculate_rank_decay(user_data)
    assert decay > 0


def test_leaderboard_applies_decay(mock_db) -> None:
    """Verify that get_leaderboard_data applies decay to ELO."""
    # User 1: Active, 1200 ELO
    STARTING_ELO = 1200
    mock_db.collection("users").document("u1").set(
        {
            "username": "active",
            "stats": {"elo": STARTING_ELO, "wins": 5, "losses": 0},
            "last_match_date": datetime.now(timezone.utc),
        },
    )

    # User 2: Inactive (60 days), 1250 ELO
    INACTIVE_ELO = 1250
    mock_db.collection("users").document("u2").set(
        {
            "username": "inactive",
            "stats": {"elo": INACTIVE_ELO, "wins": 5, "losses": 0},
            "last_match_date": datetime.now(timezone.utc) - timedelta(days=60),
        },
    )

    leaderboard = MatchRecordService.get_leaderboard_data(mock_db, min_games=0)

    u1 = next(u for u in leaderboard if u["id"] == "u1")
    u2 = next(u for u in leaderboard if u["id"] == "u2")

    # MatchRecordService uses 'elo' as the field name in the returned dict
    assert u1["elo"] == STARTING_ELO  # type: ignore
    assert u2["elo"] < INACTIVE_ELO  # type: ignore
    assert u2["is_inactive"] is True  # type: ignore
