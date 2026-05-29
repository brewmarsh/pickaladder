"""Tests for the tournament pairing generator."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pickaladder.tournament.services.generator import TournamentGenerator


class TournamentGeneratorTestCase(unittest.TestCase):
    """Test case for tournament pairing generation logic."""

    def test_next_power_of_2(self) -> None:
        """Verify the power of 2 calculation."""
        assert TournamentGenerator._next_power_of_2(1) == 1
        assert TournamentGenerator._next_power_of_2(2) == 2
        assert TournamentGenerator._next_power_of_2(3) == 4
        assert TournamentGenerator._next_power_of_2(4) == 4
        assert TournamentGenerator._next_power_of_2(5) == 8
        assert TournamentGenerator._next_power_of_2(8) == 8

    @patch("firebase_admin.firestore.client")
    def test_generate_single_elimination_perfect_power(self, mock_client) -> None:
        """Test generation for 4 participants (perfect bracket)."""
        seeds = ["p1", "p2", "p3", "p4"]
        pairings = TournamentGenerator.generate_single_elimination(seeds)

        # 4 participants -> 2 matches in R1 + 1 match in R2 = 3 matches total
        assert len(pairings) == 3

        # Round 1 Match 1: Seed 1 vs Seed 4
        assert pairings[0]["participants"] == ["p1", "p4"]
        assert pairings[0]["round"] == 1

        # Round 2 Placeholder
        assert pairings[2]["round"] == 2
        assert pairings[2]["status"] == "WAITING"

    @patch("firebase_admin.firestore.client")
    def test_generate_single_elimination_with_byes(self, mock_client) -> None:
        """Test generation for 5 participants (3 byes)."""
        seeds = ["p1", "p2", "p3", "p4", "p5"]
        pairings = TournamentGenerator.generate_single_elimination(seeds)

        # 5 participants -> size 8 -> 4 (R1) + 2 (R2) + 1 (R3) = 7 matches total
        assert len(pairings) == 7

        # Match 1: p1 vs None (Bye)
        assert pairings[0].get("isBye")
        assert pairings[0]["status"] == "COMPLETED"

        # Match 4: p4 vs p5 (Real Match)
        assert pairings[3]["participants"] == ["p4", "p5"]
        assert pairings[3]["status"] == "DRAFT"


if __name__ == "__main__":
    unittest.main()
