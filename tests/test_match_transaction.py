"""Tests for the match transaction logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.match.services import MatchService


class MatchTransactionTestCase(unittest.TestCase):
    """Test case for the match transaction logic."""

    def test_record_match_batch_singles(self) -> None:
        """Test that singles match updates user stats and elo using batch."""
        db = MagicMock()
        batch = MagicMock()
        match_ref = MagicMock()
        p1_ref = MagicMock()
        p1_ref.id = "p1"
        p2_ref = MagicMock()
        p2_ref.id = "p2"
        user_ref = MagicMock()

        # Mock snapshots
        p1_snap = MagicMock()
        p1_snap.id = "p1"
        p1_snap.exists = True
        p1_snap.to_dict.return_value = {
            "stats": {"wins": 5, "losses": 2, "elo": 1200.0},
        }

        p2_snap = MagicMock()
        p2_snap.id = "p2"
        p2_snap.exists = True
        p2_snap.to_dict.return_value = {
            "stats": {"wins": 3, "losses": 4, "elo": 1100.0},
        }

        db.get_all.return_value = [p1_snap, p2_snap]

        match_data = {
            "player1Score": 11,
            "player2Score": 5,
        }

        MatchService._record_match_batch(
            db,
            batch,
            match_ref,
            p1_ref,
            p2_ref,
            user_ref,
            match_data,
            "singles",
        )

        # Verify snapshots were read via db.get_all
        actual_args = db.get_all.call_args[0][0]
        self.assertCountEqual(actual_args, [p1_ref, p2_ref])

        # Verify match data updates
        assert match_data["winner"] == "team1"

        # Verify writes
        batch.set.assert_called_with(match_ref, match_data)

        # Verify p1 updates (win)
        p1_call_args = batch.update.call_args_list[0]
        assert p1_call_args[0][0] == p1_ref
        p1_updates = p1_call_args[0][1]
        assert p1_updates["stats.wins"] == 6
        assert p1_updates["stats.losses"] == 2
        self.assertAlmostEqual(p1_updates["stats.elo"], 1211.52, places=2)

        # Verify p2 updates (loss)
        p2_call_args = batch.update.call_args_list[1]
        assert p2_call_args[0][0] == p2_ref
        p2_updates = p2_call_args[0][1]
        assert p2_updates["stats.wins"] == 3
        assert p2_updates["stats.losses"] == 5
        self.assertAlmostEqual(p2_updates["stats.elo"], 1088.48, places=2)

        # Verify user update
        user_call_args = batch.update.call_args_list[2]
        assert user_call_args[0][0] == user_ref
        assert user_call_args[0][1] == {"lastMatchRecordedType": "singles"}

    def test_record_match_batch_doubles(self) -> None:
        """Test that doubles match updates team stats and elo using batch."""
        db = MagicMock()
        batch = MagicMock()
        match_ref = MagicMock()
        t1_ref = MagicMock()
        t1_ref.id = "t1"
        t2_ref = MagicMock()
        t2_ref.id = "t2"
        user_ref = MagicMock()

        # Mock snapshots
        t1_snap = MagicMock()
        t1_snap.id = "t1"
        t1_snap.exists = True
        t1_snap.to_dict.return_value = {
            "stats": {"wins": 10, "losses": 10, "elo": 1500.0},
        }

        t2_snap = MagicMock()
        t2_snap.id = "t2"
        t2_snap.exists = True
        t2_snap.to_dict.return_value = {
            "stats": {"wins": 20, "losses": 5, "elo": 1500.0},
        }

        db.get_all.return_value = [t1_snap, t2_snap]

        match_data = {
            "player1Score": 5,
            "player2Score": 11,
        }

        MatchService._record_match_batch(
            db,
            batch,
            match_ref,
            t1_ref,
            t2_ref,
            user_ref,
            match_data,
            "doubles",
        )

        assert match_data["winner"] == "team2"

        # Verify t1 updates (loss)
        t1_call_args = batch.update.call_args_list[0]
        assert t1_call_args[0][0] == t1_ref
        t1_updates = t1_call_args[0][1]
        assert t1_updates["stats.wins"] == 10
        assert t1_updates["stats.losses"] == 11
        assert t1_updates["stats.elo"] == 1484.0

        # Verify t2 updates (win)
        t2_call_args = batch.update.call_args_list[1]
        assert t2_call_args[0][0] == t2_ref
        t2_updates = t2_call_args[0][1]
        assert t2_updates["stats.wins"] == 21
        assert t2_updates["stats.losses"] == 5
        assert t2_updates["stats.elo"] == 1516.0

    def test_record_match_batch_with_named_teams(self) -> None:
        """Test that named teams also get updated if present."""
        db = MagicMock()
        batch = MagicMock()
        match_ref = MagicMock()
        t1_ref = MagicMock()
        t1_ref.id = "pairing1"
        t2_ref = MagicMock()
        t2_ref.id = "pairing2"
        user_ref = MagicMock()

        nt1_ref = MagicMock()
        nt1_ref.id = "named_team1"
        nt2_ref = MagicMock()
        nt2_ref.id = "named_team2"

        db.collection.return_value.document.side_effect = lambda x: {
            "pairing1": t1_ref,
            "pairing2": t2_ref,
            "named_team1": nt1_ref,
            "named_team2": nt2_ref,
            "user1": MagicMock(),
        }.get(x, MagicMock())

        # Mock snapshots
        def mock_snap(sid, elo):
            s = MagicMock()
            s.id = sid
            s.exists = True
            s.to_dict.return_value = {"stats": {"wins": 0, "losses": 0, "elo": elo}}
            return s

        snaps = [
            mock_snap("pairing1", 1200.0),
            mock_snap("pairing2", 1200.0),
            mock_snap("named_team1", 1000.0),
            mock_snap("named_team2", 1000.0),
        ]
        db.get_all.return_value = snaps

        match_data = {
            "player1Score": 11,
            "player2Score": 0,
            "namedTeam1Id": "named_team1",
            "namedTeam2Id": "named_team2",
            "participants": ["user1"],  # To avoid empty list issues
        }

        MatchService._record_match_batch(
            db,
            batch,
            match_ref,
            t1_ref,
            t2_ref,
            user_ref,
            match_data,
            "doubles",
        )

        # We expect 7 updates:
        # 1. p1 (pairing1)
        # 2. p2 (pairing2)
        # 3. nt1 (named_team1)
        # 4. nt2 (named_team2)
        # 5. user stats batch (users in team1)
        # Wait, we didn't mock team1 in match_data
        # 6. lastMatchRecordedType for user_ref
        # 7. last_match_date for each participant

        # Let's check specifically for the named team updates
        # They should be at indices 2 and 3 if they follow p1/p2

        # Pairing 1 update (win)
        assert batch.update.call_args_list[0][0][0] == t1_ref
        assert batch.update.call_args_list[0][0][1]["stats.wins"] == 1
        assert batch.update.call_args_list[0][0][1]["stats.elo"] == 1216.0

        # Pairing 2 update (loss)
        assert batch.update.call_args_list[1][0][0] == t2_ref
        assert batch.update.call_args_list[1][0][1]["stats.losses"] == 1
        assert batch.update.call_args_list[1][0][1]["stats.elo"] == 1184.0

        # Named Team 1 update (win)
        assert batch.update.call_args_list[2][0][0] == nt1_ref
        assert batch.update.call_args_list[2][0][1]["stats.wins"] == 1
        assert batch.update.call_args_list[2][0][1]["stats.elo"] == 1016.0

        # Named Team 2 update (loss)
        assert batch.update.call_args_list[3][0][0] == nt2_ref
        assert batch.update.call_args_list[3][0][1]["stats.losses"] == 1
        assert batch.update.call_args_list[3][0][1]["stats.elo"] == 984.0


if __name__ == "__main__":
    unittest.main()
