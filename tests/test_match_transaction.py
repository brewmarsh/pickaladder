"""Tests for the match transaction logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.match.services import MatchService


class MatchTransactionTestCase(unittest.TestCase):
    """Test case for the match transaction logic."""

    def test_record_match_transaction_singles(self) -> None:
        """Test that singles match updates user stats and elo."""
        transaction = MagicMock()
        match_ref = MagicMock()
        p1_ref = MagicMock()
        p2_ref = MagicMock()
        user_ref = MagicMock()

        # Mock snapshots
        p1_snap = MagicMock()
        p1_snap.to_dict.return_value = {"stats": {"wins": 5, "losses": 2, "elo": 1200.0}}
        p1_ref.get.return_value = p1_snap

        p2_snap = MagicMock()
        p2_snap.to_dict.return_value = {"stats": {"wins": 3, "losses": 4, "elo": 1100.0}}
        p2_ref.get.return_value = p2_snap

        match_data = {
            "player1Score": 11,
            "player2Score": 5,
        }

        # We call it directly since we are passing a MagicMock as transaction.
        # The decorator usually calls the function with the transaction.

        MatchService._record_match_transaction(
            transaction, match_ref, p1_ref, p2_ref, user_ref, match_data, "singles"
        )

        # Verify snapshots were read with transaction
        p1_ref.get.assert_called_with(transaction=transaction)
        p2_ref.get.assert_called_with(transaction=transaction)

        # Verify match data updates
        self.assertEqual(match_data["winner"], "team1")

        # Verify writes
        transaction.set.assert_called_with(match_ref, match_data)

        # Verify p1 updates (win)
        # Expected Elo: 1200 + 32 * (1 - (1 / (1 + 10**((1100-1200)/400))))
        # expected_p1 = 1 / (1 + 10**(-100/400)) = 1 / (1 + 10**-0.25) approx 0.64
        # new_elo = 1200 + 32 * (1 - 0.64) approx 1211.5

        p1_call_args = transaction.update.call_args_list[0]
        self.assertEqual(p1_call_args[0][0], p1_ref)
        p1_updates = p1_call_args[0][1]
        self.assertEqual(p1_updates["stats.wins"], 6)
        self.assertEqual(p1_updates["stats.losses"], 2)
        self.assertAlmostEqual(p1_updates["stats.elo"], 1211.52, places=2)

        # Verify p2 updates (loss)
        p2_call_args = transaction.update.call_args_list[1]
        self.assertEqual(p2_call_args[0][0], p2_ref)
        p2_updates = p2_call_args[0][1]
        self.assertEqual(p2_updates["stats.wins"], 3)
        self.assertEqual(p2_updates["stats.losses"], 5)
        self.assertAlmostEqual(p2_updates["stats.elo"], 1088.48, places=2)

        # Verify user update
        user_call_args = transaction.update.call_args_list[2]
        self.assertEqual(user_call_args[0][0], user_ref)
        self.assertEqual(user_call_args[0][1], {"lastMatchRecordedType": "singles"})

    def test_record_match_transaction_doubles(self) -> None:
        """Test that doubles match updates team stats and elo."""
        transaction = MagicMock()
        match_ref = MagicMock()
        t1_ref = MagicMock()
        t2_ref = MagicMock()
        user_ref = MagicMock()

        # Mock snapshots
        t1_snap = MagicMock()
        t1_snap.to_dict.return_value = {"stats": {"wins": 10, "losses": 10, "elo": 1500.0}}
        t1_ref.get.return_value = t1_snap

        t2_snap = MagicMock()
        t2_snap.to_dict.return_value = {"stats": {"wins": 20, "losses": 5, "elo": 1500.0}}
        t2_ref.get.return_value = t2_snap

        match_data = {
            "player1Score": 5,
            "player2Score": 11,
        }

        MatchService._record_match_transaction(
            transaction, match_ref, t1_ref, t2_ref, user_ref, match_data, "doubles"
        )

        self.assertEqual(match_data["winner"], "team2")

        # Verify p1 updates (loss)
        p1_call_args = transaction.update.call_args_list[0]
        self.assertEqual(p1_call_args[0][0], t1_ref)
        p1_updates = p1_call_args[0][1]
        self.assertEqual(p1_updates["stats.wins"], 10)
        self.assertEqual(p1_updates["stats.losses"], 11)
        self.assertEqual(p1_updates["stats.elo"], 1484.0)

        # Verify p2 updates (win)
        p2_call_args = transaction.update.call_args_list[1]
        self.assertEqual(p2_call_args[0][0], t2_ref)
        p2_updates = p2_call_args[0][1]
        self.assertEqual(p2_updates["stats.wins"], 21)
        self.assertEqual(p2_updates["stats.losses"], 5)
        self.assertEqual(p2_updates["stats.elo"], 1516.0)

if __name__ == "__main__":
    unittest.main()
