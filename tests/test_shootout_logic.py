"""Tests for Shootout court movement logic."""

import pytest
from pickaladder.group.services.shootout_service import ShootoutService

def test_initial_court_grouping():
    """Verify that players are initially grouped into courts by rank."""
    player_uids = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]
    assignments = ShootoutService.group_players_to_courts(player_uids, players_per_court=4)
    
    assert len(assignments) == 8
    assert assignments[0] == {"uid": "p1", "court": 1}
    assert assignments[3] == {"uid": "p4", "court": 1}
    assert assignments[4] == {"uid": "p5", "court": 2}
    assert assignments[7] == {"uid": "p8", "court": 2}

def test_shootout_movement_up_and_down():
    """Verify court movement: winners up, losers down."""
    # Court 1: p1, p2 (won) | p3, p4 (lost)
    # Court 2: p5, p6 (won) | p7, p8 (lost)
    results = [
        {"uid": "p1", "court": 1, "won": True},
        {"uid": "p2", "court": 1, "won": True},
        {"uid": "p3", "court": 1, "won": False},
        {"uid": "p4", "court": 1, "won": False},
        {"uid": "p5", "court": 2, "won": True},
        {"uid": "p6", "court": 2, "won": True},
        {"uid": "p7", "court": 2, "won": False},
        {"uid": "p8", "court": 2, "won": False},
    ]
    
    next_assignments = ShootoutService.calculate_next_assignments(results)
    next_map = {a["uid"]: a["next_court"] for a in next_assignments}
    
    # Winners on Court 1 stay on Court 1
    assert next_map["p1"] == 1
    assert next_map["p2"] == 1
    
    # Losers on Court 1 move to Court 2
    assert next_map["p3"] == 2
    assert next_map["p4"] == 2
    
    # Winners on Court 2 move to Court 1
    assert next_map["p5"] == 1
    assert next_map["p6"] == 1
    
    # Losers on Court 2 stay on Court 2
    assert next_map["p7"] == 2
    assert next_map["p8"] == 2

def test_shootout_empty_results():
    """Verify shootout logic handles empty input."""
    assert ShootoutService.calculate_next_assignments([]) == []
