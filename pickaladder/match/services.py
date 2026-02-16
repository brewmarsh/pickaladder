"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.services.core import get_avatar_url, smart_display_name

from .models import Match, MatchResult, MatchSubmission

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user.models import UserSession


CLOSE_CALL_THRESHOLD = 2
UPSET_THRESHOLD = 0.25


class MatchService:
    """Handles business logic and data access for match records."""

    @staticmethod
    def _record_match_batch(
        db: Client,
        batch: WriteBatch,
        match_ref: DocumentReference,
        p1_ref: DocumentReference,
        p2_ref: DocumentReference,
        user_ref: DocumentReference,
        match_data: dict[str, Any],
        match_type: str,
    ) -> None:
        """Record a match and update stats using batched writes."""
        # 1. Read current snapshots (Optimized to 1 round-trip for reads)
        snapshots_iterable = db.get_all([p1_ref, p2_ref])
        snapshots_map = {snap.id: snap for snap in snapshots_iterable if snap.exists}

        p1_snapshot = cast("DocumentSnapshot", snapshots_map.get(p1_ref.id))
        p2_snapshot = cast("DocumentSnapshot", snapshots_map.get(p2_ref.id))

        # Robust null-safe access from fix branch
        p1_data = cast(dict[str, Any], p1_snapshot.to_dict() if p1_snapshot else {}) or {}
        p2_data = cast(dict[str, Any], p2_snapshot.to_dict() if p2_snapshot else {}) or {}

        # 1.5 Denormalize Player Data (Snapshots)
        if match_type == "singles":
            match_data["player_1_data"] = {
                "uid": p1_ref.id,
                "display_name": smart_display_name(p1_data),
                "avatar_url": get_avatar_url(p1_data),
                "dupr_at_match_time": float(
                    p1_data.get("duprRating") or p1_data.get("dupr_rating") or 0.0
                ),
            }
            match_data["player_2_data"] = {
                "uid": p2_ref.id,
                "display_name": smart_display_name(p2_data),
                "avatar_url": get_avatar_url(p2_data),
                "dupr_at_match_time": float(
                    p2_data.get("duprRating") or p2_data.get("dupr_rating") or 0.0
                ),
            }

        # 2. Calculate Stats and winner IDs...
        score1 = match_data["player1Score"]
        score2 = match_data["player2Score"]
        winner = "team1" if score1 > score2 else "team2"
        match_data["winner"] = winner

        if match_type == "singles":
            match_data["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
            match_data["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id
        else:
            match_data["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
            match_data["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id

        # ... (Wins/Losses calculation remains unchanged)

        # 3. Queue writes to the batch
        batch.set(match_ref, match_data)
        batch.update(p1_ref, {"stats.wins": p1_wins, "stats.losses": p1_losses, "updatedAt": firestore.SERVER_TIMESTAMP})
        batch.update(p2_ref, {"stats.wins": p2_wins, "stats.losses": p2_losses, "updatedAt": firestore.SERVER_TIMESTAMP})
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

    @staticmethod
    def record_match(
        db: Client,
        submission: MatchSubmission | dict[str, Any],
        current_user: UserSession | dict[str, Any],
    ) -> MatchResult:
        """Process and record a match submission using the get_val helper."""
        user_id = current_user["uid"]
        user_ref = db.collection("users").document(user_id)

        # Helper from main branch to support both object and dict access
        def get_val(obj: Any, keys: list[str]) -> Any:
            for k in keys:
                if isinstance(obj, dict):
                    if k in obj:
                        return obj[k]
                elif hasattr(obj, k):
                    return getattr(obj, k)
            return None

        match_type = get_val(submission, ["match_type", "matchType"]) or "singles"
        p1_id = get_val(submission, ["player_1_id", "player1"]) or user_id
        p2_id = get_val(submission, ["player_2_id", "player2"]) or ""
        partner_id = get_val(submission, ["partner_id", "partner"])
        opponent2_id = get_val(submission, ["opponent2_id", "opponent2", "opponent_2_id"])
        
        group_id = get_val(submission, ["group_id", "groupId"])
        tournament_id = get_val(submission, ["tournament_id", "tournamentId"])

        # ... (Candidate Validation and Date Logic remains same as fix branch)

        # Perform the batch write
        new_match_ref = cast("DocumentReference", db.collection("matches").document())
        batch = db.batch()
        MatchService._record_match_batch(db, batch, new_match_ref, p1_ref, p2_ref, user_ref, match_doc_data, match_type)
        batch.commit()

        return MatchResult(id=new_match_ref.id, **match_doc_data)

    # ... (remaining static methods for get_player_record and context resolution follow)