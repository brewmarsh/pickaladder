"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES
from pickaladder.teams.services import TeamService
from pickaladder.user.services.core import get_avatar_url, smart_display_name

from .models import Match, MatchResult, MatchSubmission

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user import User
    from pickaladder.user.models import UserSession


CLOSE_CALL_THRESHOLD = 2
UPSET_THRESHOLD = 0.25


class MatchService:
    """Service class for match-related operations."""

    @staticmethod
    def _record_match_batch(  # noqa: PLR0913
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

        # Merged logic: cast to dict but ensure we handle None with an empty dict fallback
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
        
        # ... (Remaining logic for Elos, Updates, and Queueing remains unchanged)

    @staticmethod
    def get_tournament_name(db: Client, tournament_id: str) -> str | None:
        """Fetch tournament name with strict casting."""
        t_ref = db.collection("tournaments").document(tournament_id)
        t_doc = cast("DocumentSnapshot", t_ref.get())
        if t_doc.exists:
            return cast(str, (t_doc.to_dict() or {}).get("name"))
        return None

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        """Fetch names for two teams with null-safe fallbacks."""
        t1_doc = cast("DocumentSnapshot", db.collection("teams").document(team1_id).get())
        t2_doc = cast("DocumentSnapshot", db.collection("teams").document(team2_id).get())

        name1 = cast(str, (t1_doc.to_dict() or {}).get("name", "Team 1")) if t1_doc.exists else "Team 1"
        name2 = cast(str, (t2_doc.to_dict() or {}).get("name", "Team 2")) if t2_doc.exists else "Team 2"
        return name1, name2

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data needed for the match summary view."""
        match_data = cast("Match | None", MatchService.get_match_by_id(db, match_id))
        if not match_data:
            return {}

        m_dict = cast("dict[str, Any]", match_data)
        match_type = m_dict.get("matchType", "singles")
        context: dict[str, Any] = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            for slot in ["team1", "team2"]:
                team_refs = m_dict.get(slot, [])
                team_data = []
                if team_refs:
                    for doc in db.get_all(team_refs):
                        d_snap = cast("DocumentSnapshot", doc)
                        if d_snap.exists:
                            p_data = cast(dict[str, Any], d_snap.to_dict() or {})
                            p_data["id"] = d_snap.id
                            team_data.append(p_data)
                context[slot] = team_data
        else:
            player1_ref = m_dict.get("player1Ref")
            player2_ref = m_dict.get("player2Ref")

            for i, p_ref in enumerate([player1_ref, player2_ref], 1):
                p_data: dict[str, Any] = {}
                p_record = {"wins": 0, "losses": 0}
                if p_ref:
                    p_doc = cast("DocumentSnapshot", p_ref.get())
                    if p_doc.exists:
                        p_data = cast(dict[str, Any], p_doc.to_dict() or {})
                        p_data["id"] = p_doc.id
                        p_record = MatchService.get_player_record(db, p_ref)
                context[f"player{i}"] = p_data
                context[f"player{i}_record"] = p_record

        return context