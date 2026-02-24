from __future__ import annotations
from typing import TYPE_CHECKING, Any, cast
from .record_service import MatchRecordService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from pickaladder.match.models import Match

class MatchSummaryService:
    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data needed for the match summary view."""
        from .base_query import MatchBaseQueryService
        match_data = MatchBaseQueryService.get_match_by_id(db, match_id)
        if not match_data:
            return {}

        match_type = cast(dict[str, Any], match_data).get("matchType", "singles")
        context = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            context.update(
                MatchSummaryService._get_doubles_summary_context(db, match_data)
            )
        else:
            context.update(
                MatchSummaryService._get_singles_summary_context(db, match_data)
            )
        return context

    @staticmethod
    def _get_doubles_summary_context(db: Client, match_data: Match) -> dict[str, Any]:
        """Fetch doubles-specific context for match summary."""
        def fetch_team(refs):
            team_data = []
            if refs:
                for doc in db.get_all(refs):
                    d_snap = cast("DocumentSnapshot", doc)
                    if d_snap.exists:
                        d = d_snap.to_dict() or {}
                        d["id"] = d_snap.id
                        team_data.append(d)
            return team_data

        return {
            "team1": fetch_team(cast(dict[str, Any], match_data).get("team1", [])),
            "team2": fetch_team(cast(dict[str, Any], match_data).get("team2", [])),
        }

    @staticmethod
    def _get_singles_summary_context(db: Client, match_data: Match) -> dict[str, Any]:
        """Fetch singles-specific context for match summary."""
        res = {}
        for key, ref_key in [("player1", "player1Ref"), ("player2", "player2Ref")]:
            ref = cast(dict[str, Any], match_data).get(ref_key)
            data: dict[str, Any] = {}
            record = {"wins": 0, "losses": 0}
            if ref:
                snap = cast("DocumentSnapshot", ref.get())
                if snap.exists:
                    data = snap.to_dict() or {}
                    data["id"] = snap.id
                    record = MatchRecordService.get_player_record(db, ref)
            res[key] = data
            res[f"{key}_record"] = record
        return res
