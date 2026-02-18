"""Tests for match recording transactions."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService


class TestMatchTransaction(unittest.TestCase):
    """Test case for match recording atomic operations."""

    def test_record_match_batch_singles(self) -> None:
        """Test the internal _record_match_batch for singles."""
        db = MagicMock()
        batch = MagicMock()
        db.batch.return_value = batch

        # Mock refs
        p1_ref = MagicMock()
        p1_ref.id = "p1"
        p2_ref = MagicMock()
        p2_ref.id = "p2"
        match_ref = MagicMock()
        match_ref.id = "m1"
        db.collection().document.side_effect = lambda x=None: {
            "p1": p1_ref,
            "p2": p2_ref,
        }.get(x, match_ref)

        # Mock snapshots for stats update
        p1_snap = MagicMock()
        p1_snap.exists = True
        p1_snap.to_dict.return_value = {"wins": 0, "losses": 0}
        p2_snap = MagicMock()
        p2_snap.exists = True
        p2_snap.to_dict.return_value = {"wins": 0, "losses": 0}
        db.get_all.return_value = [p1_snap, p2_snap]

        submission = MatchSubmission(
            match_type="singles",
            player_1_id="p1",
            player_2_id="p2",
            score_p1=11,
            score_p2=5,
        )

        result = MatchService._record_match_batch(db, submission, "creator")

        # Verify result
        self.assertEqual(result.id, match_ref.id)
        self.assertEqual(result.winner, "team1")
        self.assertEqual(result.winnerId, "p1")

        # Verify batch.set was called for the match
        batch.set.assert_called()
        # Verify batch.update was called for stats
        batch.update.assert_called()

    def test_record_match_batch_doubles(self) -> None:
        """Test the internal _record_match_batch for doubles."""
        db = MagicMock()
        batch = MagicMock()
        db.batch.return_value = batch

        # Mock TeamService.get_or_create_team
        with unittest.mock.patch(
            "pickaladder.match.services.TeamService.get_or_create_team"
        ) as mock_get_team:
            mock_get_team.side_effect = ["t1", "t2"]

            submission = MatchSubmission(
                match_type="doubles",
                player_1_id="p1",
                partner_id="p2",
                player_2_id="p3",
                opponent_2_id="p4",
                score_p1=11,
                score_p2=5,
            )

            result = MatchService._record_match_batch(db, submission, "creator")

            self.assertEqual(result.matchType, "doubles")
            self.assertEqual(result.winnerId, "t1")
            batch.set.assert_called()


if __name__ == "__main__":
    unittest.main()
