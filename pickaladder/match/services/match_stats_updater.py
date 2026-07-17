from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.document import DocumentReference


class MatchStatsUpdater:
    @staticmethod
    def update_user_stats_batch(
        batch: WriteBatch,
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
    def apply_stats_delta(
        data: dict[str, Any],
        s1_won: bool,
        delta: int,
        batch: WriteBatch | None = None,
    ) -> None:
        """Apply a win/loss delta to all relevant participants."""
        match_type = data.get("matchType", "singles")
        if match_type == "doubles":
            r1, r2 = data.get("team1Ref"), data.get("team2Ref")
            u1, u2 = data.get("team1", []), data.get("team2", [])
            MatchStatsUpdater._increment_stats(r1, r2, s1_won, delta, batch)
            for ref in u1:
                MatchStatsUpdater._increment_stats(ref, None, s1_won, delta, batch)
            for ref in u2:
                MatchStatsUpdater._increment_stats(None, ref, s1_won, delta, batch)

            # Phase 8: Support for Named Teams
            nt1_id = data.get("namedTeam1Id")
            nt2_id = data.get("namedTeam2Id")
            if nt1_id or nt2_id:
                db = firestore.client()
                nt1_ref = db.collection("teams").document(nt1_id) if nt1_id else None
                nt2_ref = db.collection("teams").document(nt2_id) if nt2_id else None
                MatchStatsUpdater._increment_stats(nt1_ref, nt2_ref, s1_won, delta, batch)
        else:
            r1, r2 = data.get("player1Ref"), data.get("player2Ref")
            MatchStatsUpdater._increment_stats(r1, r2, s1_won, delta, batch)

    @staticmethod
    def _increment_stats(
        r1: DocumentReference | None,
        r2: DocumentReference | None,
        s1_won: bool,
        delta: int,
        batch: WriteBatch | None = None,
    ) -> None:
        """Helper to increment/decrement wins and losses on two references."""
        if r1:
            field = "stats.wins" if s1_won else "stats.losses"
            if batch:
                batch.update(r1, {field: firestore.Increment(delta)})
            else:
                r1.update({field: firestore.Increment(delta)})
        if r2:
            field = "stats.wins" if not s1_won else "stats.losses"
            if batch:
                batch.update(r2, {field: firestore.Increment(delta)})
            else:
                r2.update({field: firestore.Increment(delta)})
