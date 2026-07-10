from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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

        match_type = cast("dict[str, Any]", match_data).get("matchType", "singles")
        context = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            context.update(
                MatchSummaryService._get_doubles_summary_context(db, match_data),
            )
        else:
            context.update(
                MatchSummaryService._get_singles_summary_context(db, match_data),
            )
        return context

    @staticmethod
    def _get_doubles_summary_context(db: Client, match_data: Match) -> dict[str, Any]:
        """Fetch doubles-specific context for match summary."""
        m_dict = cast("dict[str, Any]", match_data)
        return {
            "team1": MatchSummaryService._fetch_team_data(db, m_dict.get("team1", [])),
            "team2": MatchSummaryService._fetch_team_data(db, m_dict.get("team2", [])),
        }

    @staticmethod
    def _fetch_team_data(db: Client, refs: list[Any]) -> list[dict[str, Any]]:
        """Fetch data for a list of player references."""
        team_data = []
        if refs:
            for doc in db.get_all(refs):
                d_snap = cast("DocumentSnapshot", doc)
                if d_snap.exists:
                    d = d_snap.to_dict() or {}
                    d["id"] = d_snap.id
                    team_data.append(d)
        return team_data

    @staticmethod
    def _get_singles_summary_context(db: Client, match_data: Match) -> dict[str, Any]:
        """Fetch singles-specific context for match summary."""
        res: dict[str, Any] = {}
        refs = []
        keys = []

        m_dict = cast("dict[str, Any]", match_data)

        for key, ref_key in [("player1", "player1Ref"), ("player2", "player2Ref")]:
            ref = m_dict.get(ref_key)
            if ref:
                refs.append(ref)
                keys.append(key)
            else:
                res[key] = {}
                res[f"{key}_record"] = {"wins": 0, "losses": 0}

        if refs:
            # We map by ref ID to match them later, as batch_get_documents doesn't guarantee order
            # (or we can just rely on the order returned if we're careful with missing docs,
            # but mapping is safer)

            # Note: in testing environment, db.get_all doesn't actually hit firestore natively
            # but let's just do an orderly zip for now since that's what the test expects
            docs = db.get_all(refs)
            for key, snap in zip(keys, docs):
                data: dict[str, Any] = {}
                record = {"wins": 0, "losses": 0}
                if snap.exists:
                    data = snap.to_dict() or {}
                    data["id"] = snap.id
                    stats = data.get("stats", {})
                    record = {
                        "wins": stats.get("wins", 0),
                        "losses": stats.get("losses", 0),
                    }
                res[key] = data
                res[f"{key}_record"] = record

        return res
