"""Tests for the StandingAggregator."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.core.ranking.aggregator import StandingAggregator


class StandingAggregatorTestCase(unittest.TestCase):
    """Test cases for hierarchical standing aggregation."""

    def test_basic_aggregation(self) -> None:
        """Test simple win/loss and point diff aggregation."""
        p1_ref = MagicMock(id="p1")
        p2_ref = MagicMock(id="p2")

        matches = [
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Ref": p1_ref,
                "player2Ref": p2_ref,
                "player1Score": 11,
                "player2Score": 5,
            },
        ]

        standings = StandingAggregator.aggregate(["p1", "p2"], matches)

        assert len(standings) == 2
        assert standings[0]["uid"] == "p1"
        assert standings[0]["wins"] == 1
        assert standings[0]["point_diff"] == 6

        assert standings[1]["uid"] == "p2"
        assert standings[1]["losses"] == 1
        assert standings[1]["point_diff"] == -6

    def test_h2h_tie_breaker(self) -> None:
        """Test that H2H breaks a tie when wins are equal."""
        matches = [
            # p1 beat p2 (H2H)
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Id": "p1",
                "player2Id": "p2",
                "player1Score": 11,
                "player2Score": 9,
            },
            # p1 lost to p3
            {
                "status": "COMPLETED",
                "winnerId": "p3",
                "participants": ["p1", "p3"],
                "player1Id": "p1",
                "player2Id": "p3",
                "player1Score": 5,
                "player2Score": 11,
            },
            # p2 beat p3
            {
                "status": "COMPLETED",
                "winnerId": "p2",
                "participants": ["p2", "p3"],
                "player1Id": "p2",
                "player2Id": "p3",
                "player1Score": 11,
                "player2Score": 5,
            },
        ]
        # Results:
        # p1: 1-1, H2H over p2
        # p2: 1-1, H2H over p3
        # p3: 1-1, H2H over p1
        # This is a 3-way cycle.
        # PD: p1: -4, p2: +4, p3: 0

        standings = StandingAggregator.aggregate(["p1", "p2", "p3"], matches)
        assert standings[0]["uid"] == "p2"
        assert standings[0]["tie_break_reason"] == "PD"
        assert standings[1]["uid"] == "p3"
        assert standings[1]["tie_break_reason"] == "PD"
        assert standings[2]["uid"] == "p1"
        assert standings[2]["tie_break_reason"] == "PD"

    def test_2way_tie_broken_by_h2h(self) -> None:
        """Test simple 2-way tie resolved by H2H."""
        # Setup:
        # P3: 2 wins, 0 losses (vs P1, P2)
        # P1: 1 win, 1 loss (vs P2, P3) - Beat P2
        # P2: 1 win, 1 loss (vs P4, P3) - Lost to P1
        # P4: 0 wins, 1 loss (vs P2)

        matches = [
            # P3 beats P1
            {
                "status": "COMPLETED",
                "winnerId": "p3",
                "participants": ["p3", "p1"],
                "player1Id": "p3",
                "player2Id": "p1",
                "player1Score": 11,
                "player2Score": 0,
            },
            # P3 beats P2
            {
                "status": "COMPLETED",
                "winnerId": "p3",
                "participants": ["p3", "p2"],
                "player1Id": "p3",
                "player2Id": "p2",
                "player1Score": 11,
                "player2Score": 0,
            },
            # P1 beats P2 (H2H)
            {
                "status": "COMPLETED",
                "winnerId": "p1",
                "participants": ["p1", "p2"],
                "player1Id": "p1",
                "player2Id": "p2",
                "player1Score": 11,
                "player2Score": 10,
            },
            # P2 beats P4
            {
                "status": "COMPLETED",
                "winnerId": "p2",
                "participants": ["p2", "p4"],
                "player1Id": "p2",
                "player2Id": "p4",
                "player1Score": 11,
                "player2Score": 5,
            },
        ]

        standings = StandingAggregator.aggregate(["p1", "p2", "p3", "p4"], matches)

        # Rankings:
        # 1. P3 (2-0)
        # 2. P1 (1-1) - H2H winner over P2
        # 3. P2 (1-1) - H2H loser to P1
        # 4. P4 (0-1)

        assert standings[0]["uid"] == "p3"
        assert standings[0]["tie_break_reason"] is None

        assert standings[1]["uid"] == "p1"
        assert standings[1]["tie_break_reason"] == "H2H"

        assert standings[2]["uid"] == "p2"
        assert standings[2]["tie_break_reason"] == "H2H"

        assert standings[3]["uid"] == "p4"


if __name__ == "__main__":
    unittest.main()
