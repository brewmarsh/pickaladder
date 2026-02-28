from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class MatchStatsUpdater:
    @staticmethod
    def update_user_stats_batch(
        batch: WriteBatch | Transaction,
        team1_refs: list[DocumentReference],
        team2_refs: list[DocumentReference],
        winner: str,
    ) -> None:
        """Update individual user stats in a batch for doubles matches."""
        for ref in team1_refs:
            field = "stats.wins" if winner == "team1" else "stats.losses"
            batch.update(ref, {field: firestore.Increment(1)})
        for ref in team2_refs:
            field = "stats.wins" if winner == "team2" else "stats.losses"
            batch.update(ref, {field: firestore.Increment(1)})

    @staticmethod
    def apply_stats_delta(data: dict[str, Any], s1_won: bool, delta: int) -> None:
        """Apply a win/loss delta to all relevant participants."""
        match_type = data.get("matchType", "singles")
        if match_type == "doubles":
            r1, r2 = data.get("team1Ref"), data.get("team2Ref")
            u1, u2 = data.get("team1", []), data.get("team2", [])
            MatchStatsUpdater._increment_stats(r1, r2, s1_won, delta)
            for ref in u1:
                MatchStatsUpdater._increment_stats(ref, None, s1_won, delta)
            for ref in u2:
                MatchStatsUpdater._increment_stats(None, ref, s1_won, delta)
        else:
            r1, r2 = data.get("player1Ref"), data.get("player2Ref")
            MatchStatsUpdater._increment_stats(r1, r2, s1_won, delta)

    @staticmethod
    def _increment_stats(
        r1: DocumentReference | None,
        r2: DocumentReference | None,
        s1_won: bool,
        delta: int,
    ) -> None:
        """Helper to increment/decrement wins and losses on two references."""
        if r1:
            field = "stats.wins" if s1_won else "stats.losses"
            r1.update({field: firestore.Increment(delta)})
        if r2:
            field = "stats.wins" if not s1_won else "stats.losses"
            r2.update({field: firestore.Increment(delta)})

    @staticmethod
    def update_lifetime_stats_atomic(
        transaction: Transaction,
        user_id: str,
        is_win: bool,
        db: Client,
        snapshot: DocumentSnapshot | None = None,
    ) -> None:
        """Update lifetime stats for a user atomically.

        Args:
            transaction: The transaction object.
            user_id: The user ID.
            is_win: Whether the match was a win.
            db: The Firestore client.
            snapshot: Optional pre-fetched snapshot for the lifetime stats document.
        """
        stats_ref = (
            db.collection("users").document(user_id).collection("stats").document("lifetime")
        )

        if snapshot is None:
            snapshot = stats_ref.get(transaction=transaction)

        stats = (
            snapshot.to_dict()
            if (snapshot and snapshot.exists)
            else {"total_matches": 0, "wins": 0, "losses": 0, "current_streak": 0}
        )

        stats["total_matches"] = stats.get("total_matches", 0) + 1
        streak = stats.get("current_streak", 0)

        if is_win:
            stats["wins"] = stats.get("wins", 0) + 1
            stats["current_streak"] = streak + 1 if streak > 0 else 1
        else:
            stats["losses"] = stats.get("losses", 0) + 1
            stats["current_streak"] = streak - 1 if streak < 0 else -1

        transaction.set(stats_ref, stats, merge=True)
