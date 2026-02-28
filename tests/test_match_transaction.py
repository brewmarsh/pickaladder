"""Tests for the match transaction logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from google.cloud.firestore_v1.transaction import Transaction

from pickaladder.match.services import MatchService


class MatchTransactionTestCase(unittest.TestCase):
    """Test case for the match transaction logic."""

    def test_record_match_atomic_singles(self) -> None:
        """Test that singles match updates user stats and elo using transaction."""
        db = MagicMock()
        transaction = MagicMock(spec=Transaction)
        match_ref = MagicMock()

        # Helper to create mock refs with path
        def create_mock_ref(path):
            ref = MagicMock()
            ref.path = path
            ref.id = path.split("/")[-1]
            return ref

        p1_ref = create_mock_ref("users/p1")
        p2_ref = create_mock_ref("users/p2")
        user_ref = create_mock_ref("users/current")

        l1_ref = create_mock_ref("users/p1/stats/lifetime")
        l2_ref = create_mock_ref("users/p2/stats/lifetime")

        # Mock Firestore hierarchy
        def db_collection_side_effect(name):
            col = MagicMock()
            def col_document_side_effect(doc_id):
                doc_path = f"{name}/{doc_id}"
                doc_ref = create_mock_ref(doc_path)

                # Mock subcollections for user stats
                if name == "users":
                    def doc_ref_collection_side_effect(sub_name):
                        sub_col = MagicMock()
                        def sub_col_document_side_effect(sub_doc_id):
                            return create_mock_ref(f"{doc_path}/{sub_name}/{sub_doc_id}")
                        sub_col.document.side_effect = sub_col_document_side_effect
                        return sub_col
                    doc_ref.collection.side_effect = doc_ref_collection_side_effect
                return doc_ref
            col.document.side_effect = col_document_side_effect
            return col
        db.collection.side_effect = db_collection_side_effect

        # Mock snapshots
        def create_mock_snap(ref, data, exists=True):
            snap = MagicMock()
            snap.reference = ref
            snap.exists = exists
            snap.to_dict.return_value = data
            return snap

        p1_snap = create_mock_snap(p1_ref, {"stats": {"wins": 5, "losses": 2, "elo": 1200.0}})
        p2_snap = create_mock_snap(p2_ref, {"stats": {"wins": 3, "losses": 4, "elo": 1100.0}})
        l1_snap = create_mock_snap(l1_ref, {"total_matches": 7, "wins": 5, "losses": 2, "current_streak": 2})
        l2_snap = create_mock_snap(l2_ref, {"total_matches": 7, "wins": 3, "losses": 4, "current_streak": -1})

        db.get_all.return_value = [p1_snap, p2_snap, l1_snap, l2_snap]

        match_data = {
            "player1Score": 11,
            "player2Score": 5,
            "player1Ref": p1_ref,
            "player2Ref": p2_ref,
        }

        MatchService._record_match_atomic(
            db, transaction, match_ref, p1_ref, p2_ref, user_ref, match_data, "singles"
        )

        # Verify snapshots were read via db.get_all
        db.get_all.assert_called_with(unittest.mock.ANY, transaction=transaction)

        # Verify match data updates
        self.assertEqual(match_data["winner"], "team1")

        # Verify writes
        transaction.set.assert_called()

        # Verify updates (order might vary depending on dictionary iteration, but we check by ref)
        updates = {call[0][0].path: call[0][1] for call in transaction.update.call_args_list}

        self.assertEqual(updates["users/p1"]["stats.wins"], 6)
        self.assertEqual(updates["users/p2"]["stats.losses"], 5)

        # Verify lifetime stats updates
        sets = {call[0][0].path: call[0][1] for call in transaction.set.call_args_list if hasattr(call[0][0], "path")}
        self.assertEqual(sets["users/p1/stats/lifetime"]["wins"], 6)
        self.assertEqual(sets["users/p1/stats/lifetime"]["current_streak"], 3)
        self.assertEqual(sets["users/p2/stats/lifetime"]["losses"], 5)
        self.assertEqual(sets["users/p2/stats/lifetime"]["current_streak"], -2)

    def test_record_match_atomic_doubles(self) -> None:
        """Test that doubles match updates team stats and elo using transaction."""
        db = MagicMock()
        transaction = MagicMock(spec=Transaction)
        match_ref = MagicMock()

        def create_mock_ref(path):
            ref = MagicMock()
            ref.path = path
            ref.id = path.split("/")[-1]
            return ref

        t1_ref = create_mock_ref("teams/t1")
        t2_ref = create_mock_ref("teams/t2")
        user_ref = create_mock_ref("users/current")

        # Mock Firestore hierarchy
        def db_collection_side_effect(name):
            col = MagicMock()
            def col_document_side_effect(doc_id):
                doc_path = f"{name}/{doc_id}"
                doc_ref = create_mock_ref(doc_path)
                if name == "users":
                    def doc_ref_collection_side_effect(sub_name):
                        sub_col = MagicMock()
                        def sub_col_document_side_effect(sub_doc_id):
                            return create_mock_ref(f"{doc_path}/{sub_name}/{sub_doc_id}")
                        sub_col.document.side_effect = sub_col_document_side_effect
                        return sub_col
                    doc_ref.collection.side_effect = doc_ref_collection_side_effect
                return doc_ref
            col.document.side_effect = col_document_side_effect
            return col
        db.collection.side_effect = db_collection_side_effect

        # Setup mock users
        u_refs = [create_mock_ref(f"users/p{i}") for i in range(1, 5)]

        def create_mock_snap(ref, data, exists=True):
            snap = MagicMock()
            snap.reference = ref
            snap.exists = exists
            snap.to_dict.return_value = data
            return snap

        t1_snap = create_mock_snap(t1_ref, {"stats": {"wins": 10, "losses": 10, "elo": 1500.0}})
        t2_snap = create_mock_snap(t2_ref, {"stats": {"wins": 20, "losses": 5, "elo": 1500.0}})

        u_stats_snaps = [create_mock_snap(create_mock_ref(f"{r.path}/stats/lifetime"),
                                        {"total_matches": 0, "wins": 0, "losses": 0, "current_streak": 0})
                        for r in u_refs]

        db.get_all.return_value = [t1_snap, t2_snap] + u_stats_snaps

        match_data = {
            "player1Score": 5,
            "player2Score": 11,
            "team1": u_refs[:2],
            "team2": u_refs[2:],
        }

        MatchService._record_match_atomic(
            db, transaction, match_ref, t1_ref, t2_ref, user_ref, match_data, "doubles"
        )

        self.assertEqual(match_data["winner"], "team2")

        updates = {call[0][0].path: call[0][1] for call in transaction.update.call_args_list}
        self.assertEqual(updates["teams/t1"]["stats.losses"], 11)
        self.assertEqual(updates["teams/t2"]["stats.wins"], 21)


if __name__ == "__main__":
    unittest.main()
