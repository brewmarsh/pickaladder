"""Tests for ranking integrity and ELO updates."""

from pickaladder.match.services.calculator import MatchStatsCalculator


def test_elo_calculation_winner_gains_loser_drops():
    """Verify that ELO updates correctly: winner goes up, loser goes down."""
    BASE_ELO = 1200.0
    p1_data = {"stats": {"elo": BASE_ELO, "wins": 0, "losses": 0}}
    p2_data = {"stats": {"elo": BASE_ELO, "wins": 0, "losses": 0}}

    p1_upd, p2_upd = MatchStatsCalculator.calculate_elo_updates(
        "team1", p1_data, p2_data
    )

    assert p1_upd["stats.elo"] > BASE_ELO
    assert p2_upd["stats.elo"] < BASE_ELO
    assert p1_upd["stats.wins"] == 1
    assert p2_upd["stats.losses"] == 1

def test_elo_calculation_upset_yields_larger_change():
    """Verify that an upset (lower ELO wins) results in a larger rating change."""
    # Scenario 1: Even match
    p1_even = {"stats": {"elo": 1200.0}}
    p2_even = {"stats": {"elo": 1200.0}}
    upd1_even, _ = MatchStatsCalculator.calculate_elo_updates("team1", p1_even, p2_even)
    change_even = upd1_even["stats.elo"] - 1200.0

    # Scenario 2: Upset (p1 has 1000, p2 has 1400, p1 wins)
    p1_underdog = {"stats": {"elo": 1000.0}}
    p2_favorite = {"stats": {"elo": 1400.0}}
    upd1_upset, _ = MatchStatsCalculator.calculate_elo_updates(
        "team1", p1_underdog, p2_favorite
    )
    change_upset = upd1_upset["stats.elo"] - 1000.0

    assert change_upset > change_even

def test_check_upset_logic():
    """Verify upset detection based on DUPR threshold."""
    # Threshold is 0.25
    p1_weak = {"duprRating": 3.0}
    p2_strong = {"duprRating": 3.5}

    # p1 (3.0) beats p2 (3.5) -> Upset (diff 0.5 > 0.25)
    assert MatchStatsCalculator.check_upset("team1", p1_weak, p2_strong) is True

    # p2 (3.5) beats p1 (3.0) -> Not an upset
    assert MatchStatsCalculator.check_upset("team2", p1_weak, p2_strong) is False

    # Even match
    p1_even = {"duprRating": 3.5}
    assert MatchStatsCalculator.check_upset("team1", p1_even, p2_strong) is False
