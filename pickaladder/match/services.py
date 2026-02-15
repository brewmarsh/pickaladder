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

    from pickaladder.user.models import UserSession


CLOSE_CALL_THRESHOLD = 2
UPSET_THRESHOLD = 0.25


class MatchService:
    """Service class for match-related operations."""

    # ... (_record_match_batch and record_match methods remain unchanged)

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        """Fetch a mapping of UIDs to names."""
        names: dict[str, str] = {}
        if not uids:
            return names
        u_refs = [db.collection("users").document(uid) for uid in uids]
        for doc in db.get_all(u_refs):
            d_snap = cast("DocumentSnapshot", doc)
            if d_snap.exists:
                d = d_snap.to_dict() or {}
                names[str(d_snap.id)] = str(d.get("name", d_snap.id))
        return names

    @staticmethod
    def get_tournament_name(db: Client, tournament_id: str) -> str | None:
        """Fetch tournament name."""
        t_ref = db.collection("tournaments").document(tournament_id)
        t_doc = cast("DocumentSnapshot", t_ref.get())
        if t_doc.exists:
            return cast(str, (t_doc.to_dict() or {}).get("name"))
        return None

    @staticmethod
    def get_user_last_match_type(db: Client, user_id: str) -> str:
        """Fetch the last match type recorded by the user."""
        u_doc = cast("DocumentSnapshot", db.collection("users").document(user_id).get())
        if u_doc.exists:
            return cast(
                str, (u_doc.to_dict() or {}).get("lastMatchRecordedType", "singles")
            )
        return "singles"

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        """Fetch names for two teams."""
        t1_doc = cast("DocumentSnapshot", db.collection("teams").document(team1_id).get())
        t2_doc = cast("DocumentSnapshot", db.collection("teams").document(team2_id).get())

        name1 = cast(str, (t1_doc.to_dict() or {}).get("name", "Team 1")) if t1_doc.exists else "Team 1"
        name2 = cast(str, (t2_doc.to_dict() or {}).get("name", "Team 2")) if t2_doc.exists else "Team 2"
        return name1, name2

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data needed for the match summary view."""
        match_data = MatchService.get_match_by_id(db, match_id)
        if not match_data:
            return {}

        m_dict = cast("dict[str, Any]", match_data)
        match_type = m_dict.get("matchType", "singles")
        context = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            for slot in ["team1", "team2"]:
                team_refs = m_dict.get(slot, [])
                team_data = []
                if team_refs:
                    for doc in db.get_all(team_refs):
                        d_snap = cast("DocumentSnapshot", doc)
                        if d_snap.exists:
                            p_data = d_snap.to_dict() or {}
                            p_data["id"] = d_snap.id
                            team_data.append(p_data)
                context[slot] = team_data
        else:
            player1_ref = m_dict.get("player1Ref")
            player2_ref = m_dict.get("player2Ref")

            player1_data: dict[str, Any] = {}
            player2_data: dict[str, Any] = {}
            player1_record = {"wins": 0, "losses": 0}
            player2_record = {"wins": 0, "losses": 0}

            if player1_ref:
                p1_doc = cast("DocumentSnapshot", player1_ref.get())
                if p1_doc.exists:
                    p1_data = p1_doc.to_dict() or {}
                    p1_data["id"] = p1_doc.id
                    player1_record = MatchService.get_player_record(db, player1_ref)

            if player2_ref:
                p2_doc = cast("DocumentSnapshot", player2_ref.get())
                if p2_doc.exists:
                    p2_data = p2_doc.to_dict() or {}
                    p2_data["id"] = p2_doc.id
                    player2_record = MatchService.get_player_record(db, player2_ref)

            context.update({
                "player1": player1_data,
                "player2": player2_data,
                "player1_record": player1_record,
                "player2_record": player2_record,
            })

        return context