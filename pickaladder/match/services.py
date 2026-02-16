"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
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
    ) -> tuple[float, float, float]:
        """Record a match and update stats using batched writes."""
        # 1. Read snapshots and handle null safety
        snapshots_iterable = db.get_all([p1_ref, p2_ref])
        snapshots_map = {snap.id: snap for snap in snapshots_iterable if snap.exists}

        p1_snapshot = snapshots_map.get(p1_ref.id)
        p2_snapshot = snapshots_map.get(p2_ref.id)

        p1_data = cast(dict[str, Any], p1_snapshot.to_dict() if p1_snapshot else {}) or {}
        p2_data = cast(dict[str, Any], p2_snapshot.to_dict() if p2_snapshot else {}) or {}

        # 1.5 Denormalize Player Data for UI performance
        if match_type == "singles":
            for i, (ref, data) in enumerate([(p1_ref, p1_data), (p2_ref, p2_data)], 1):
                match_data[f"player_{i}_data"] = {
                    "uid": ref.id,
                    "display_name": smart_display_name(data),
                    "avatar_url": get_avatar_url(data),
                    "dupr_at_match_time": float(data.get("duprRating") or data.get("dupr_rating") or 0.0),
                }

        # 2. Calculate New Stats (Elo Algorithm)
        score1, score2 = match_data["player1Score"], match_data["player2Score"]
        winner = "team1" if score1 > score2 else "team2"
        match_data["winner"] = winner

        def get_stat(data: dict[str, Any], key: str, default: Any) -> Any:
            return data.get("stats", {}).get(key, default)

        p1_elo = float(get_stat(p1_data, "elo", 1200.0))
        p2_elo = float(get_stat(p2_data, "elo", 1200.0))

        # Elo Calculation (K=32)
        k = 32
        expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
        actual_p1 = 1.0 if winner == "team1" else 0.0
        
        new_p1_elo = p1_elo + k * (actual_p1 - expected_p1)
        new_p2_elo = p2_elo + k * ((1.0 - actual_p1) - (1.0 - expected_p1))
        elo_delta = new_p1_elo - p1_elo

        # Upset Logic
        if match_type == "singles":
            r1 = float(p1_data.get("dupr_rating") or p1_data.get("duprRating") or 0.0)
            r2 = float(p2_data.get("dupr_rating") or p2_data.get("duprRating") or 0.0)
            if r1 > 0 and r2 > 0:
                if (winner == "team1" and (r2 - r1) >= UPSET_THRESHOLD) or \
                   (winner == "team2" and (r1 - r2) >= UPSET_THRESHOLD):
                    match_data["is_upset"] = True

        # 3. Queue Writes
        batch.set(match_ref, match_data)
        batch.update(p1_ref, {
            "stats.wins": get_stat(p1_data, "wins", 0) + (1 if winner == "team1" else 0),
            "stats.losses": get_stat(p1_data, "losses", 0) + (1 if winner == "team2" else 0),
            "stats.elo": new_p1_elo,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        batch.update(p2_ref, {
            "stats.wins": get_stat(p2_data, "wins", 0) + (1 if winner == "team2" else 0),
            "stats.losses": get_stat(p2_data, "losses", 0) + (1 if winner == "team1" else 0),
            "stats.elo": new_p2_elo,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })
        
        batch.update(user_ref, {"lastMatchRecordedType": match_type})
        return new_p1_elo, new_p2_elo, elo_delta

    @staticmethod
    def _get_match_updates(match_data: dict[str, Any], new_p1_score: int, new_p2_score: int) -> dict[str, Any]:
        """Utility from main branch to calculate score-related updates."""
        winner = "team1" if new_p1_score > new_p2_score else "team2"
        updates: dict[str, Any] = {
            "player1Score": new_p1_score,
            "player2Score": new_p2_score,
            "winner": winner,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        # ... logic for singles/doubles IDs remains same as main
        return updates

    # ... (record_match and get_match_summary_context follow fix branch implementation)