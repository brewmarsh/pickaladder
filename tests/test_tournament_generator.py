"""Tests for the tournament pairing generator."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from pickaladder.tournament.services.generator import TournamentGenerator


class TournamentGeneratorTestCase(unittest.TestCase):
    """Test case for tournament pairing generation logic."""

    def test_next_power_of_2(self) -> None:
        """Verify the power of 2 calculation."""
        self.assertEqual(TournamentGenerator._next_power_of_2(1), 1)
        self.assertEqual(TournamentGenerator._next_power_of_2(2), 2)
        self.assertEqual(TournamentGenerator._next_power_of_2(3), 4)
        self.assertEqual(TournamentGenerator._next_power_of_2(4), 4)
        self.assertEqual(TournamentGenerator._next_power_of_2(5), 8)
        self.assertEqual(TournamentGenerator._next_power_of_2(8), 8)

    @patch("firebase_admin.firestore.client")
    def test_generate_single_elimination_perfect_power(self, mock_client) -> None:
        """Test generation for 4 participants (perfect bracket)."""
        seeds = ["p1", "p2", "p3", "p4"]
        pairings = TournamentGenerator.generate_single_elimination(seeds)

        # 4 participants -> 2 matches in R1 + 1 match in R2 = 3 matches total
        self.assertEqual(len(pairings), 3)

        # Round 1 Match 1: Seed 1 vs Seed 4
        self.assertEqual(pairings[0]["participants"], ["p1", "p4"])
        self.assertEqual(pairings[0]["round"], 1)

        # Round 2 Placeholder
        self.assertEqual(pairings[2]["round"], 2)
        self.assertEqual(pairings[2]["status"], "WAITING")

    @patch("firebase_admin.firestore.client")
    def test_generate_single_elimination_with_byes(self, mock_client) -> None:
        """Test generation for 5 participants (3 byes)."""
        seeds = ["p1", "p2", "p3", "p4", "p5"]
        pairings = TournamentGenerator.generate_single_elimination(seeds)

        # 5 participants -> size 8 -> 4 (R1) + 2 (R2) + 1 (R3) = 7 matches total
        self.assertEqual(len(pairings), 7)

        # Match 1: p1 vs None (Bye)
        self.assertTrue(pairings[0].get("isBye"))
        self.assertEqual(pairings[0]["status"], "COMPLETED")

        # Match 4: p4 vs p5 (Real Match)
        self.assertEqual(pairings[3]["participants"], ["p4", "p5"])
        self.assertEqual(pairings[3]["status"], "DRAFT")

if __name__ == "__main__":
    unittest.main()
