from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from pickaladder.match.models import Match

from .base_query import MatchBaseQueryService
from .candidate_service import MatchCandidateService
from .formatting import MatchFormatter
from .record_service import MatchRecordService
from .summary_service import MatchSummaryService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference


class MatchQueryService(
    MatchBaseQueryService,
    MatchCandidateService,
    MatchRecordService,
    MatchSummaryService,
):
    """Service class for match-related read operations."""

    @staticmethod
    def get_latest_matches(db: Client, limit: int = 10) -> list[Match]:
        """Fetch and process the latest matches."""
        from firebase_admin import firestore

        try:
            matches_query = (
                db.collection("matches")
                .order_by("createdAt", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            matches = list(matches_query.stream())
        except KeyError:
            # Fallback for mockfirestore
            matches = list(db.collection("matches").limit(limit).stream())

        return [MatchQueryService._process_match_document(m, db) for m in matches]

    @staticmethod
    def _process_match_document(match_doc: DocumentSnapshot, db: Client) -> Match:
        """Process a single match document into a formatted dictionary."""
        from pickaladder.match.models import Match

        match_data = cast(Any, match_doc.to_dict() or {})
        match_data["id"] = match_doc.id
        MatchFormatter.apply_common_match_formatting(match_data)

        player_refs = MatchQueryService._get_player_refs_from_matches([match_doc])
        players = MatchQueryService._fetch_player_names(db, player_refs)

        if match_data.get("matchType") == "doubles":
            MatchFormatter.format_doubles_match_names(match_data, players)
        else:
            MatchFormatter.format_singles_match_names(match_data, players)

        return Match(match_data)

    @staticmethod
    def _get_player_refs_from_matches(
        matches: list[DocumentSnapshot],
    ) -> set[DocumentReference]:
        """Extract all unique player references from a list of matches."""
        player_refs: set[DocumentReference] = set()
        for match in matches:
            m_data = match.to_dict()
            if m_data:
                player_refs.update(MatchQueryService._extract_refs_from_match(m_data))
        return player_refs

    @staticmethod
    def _extract_refs_from_match(m_data: dict[str, Any]) -> set[DocumentReference]:
        """Extract player references from a single match data dictionary."""
        if m_data.get("matchType") == "doubles":
            return MatchQueryService._extract_doubles_refs(m_data)
        return MatchQueryService._extract_singles_refs(m_data)

    @staticmethod
    def _extract_doubles_refs(m_data: dict[str, Any]) -> set[DocumentReference]:
        """Extract player references from a doubles match."""
        refs: set[DocumentReference] = set()
        refs.update(m_data.get("team1", []))
        refs.update(m_data.get("team2", []))
        return refs

    @staticmethod
    def _extract_singles_refs(m_data: dict[str, Any]) -> set[DocumentReference]:
        """Extract player references from a singles match."""
        refs: set[DocumentReference] = set()
        if "player_1_data" not in m_data or "player_2_data" not in m_data:
            if p1_ref := m_data.get("player1Ref"):
                refs.add(p1_ref)
            if p2_ref := m_data.get("player2Ref"):
                refs.add(p2_ref)
        return refs

    @staticmethod
    def _fetch_player_names(
        db: Client, player_refs: set[DocumentReference]
    ) -> dict[str, str]:
        """Fetch names for a set of player references."""
        players: dict[str, str] = {}
        if player_refs:
            player_docs = db.get_all(list(player_refs))
            for doc in player_docs:
                d_snap = cast("DocumentSnapshot", doc)
                if d_snap.exists:
                    d_data = d_snap.to_dict() or {}
                    players[d_snap.id] = d_data.get("name", "N/A")
        return players

    @staticmethod
    def get_matches_for_user(
        db: Client, uid: str, limit: int = 20, start_after: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch matches for a user with cursor-based pagination."""
        from firebase_admin import firestore

        from pickaladder.user.services.match_formatting import (
            format_matches_for_dashboard,
        )

        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("participants", "array_contains", uid))
            .order_by("matchDate", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        if start_after:
            last_doc = cast(
                "DocumentSnapshot", db.collection("matches").document(start_after).get()
            )
            if last_doc.exists:
                query = query.start_after(last_doc)

        docs = list(query.stream())
        return (
            (format_matches_for_dashboard(db, docs, uid), docs[-1].id)
            if docs
            else ([], None)
        )

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        """Fetch a mapping of UIDs to names."""
        names: dict[str, str] = {}
        if uids:
            u_refs = [db.collection("users").document(uid) for uid in uids]
            for doc in db.get_all(u_refs):
                d_snap = cast("DocumentSnapshot", doc)
                if d_snap.exists:
                    names[d_snap.id] = (d_snap.to_dict() or {}).get("name", d_snap.id)
        return names

    @staticmethod
    def get_tournament_name(db: Client, tournament_id: str) -> str | None:
        """Fetch tournament name."""
        doc = cast(
            "DocumentSnapshot",
            db.collection("tournaments").document(tournament_id).get(),
        )
        return (doc.to_dict() or {}).get("name") if doc.exists else None

    @staticmethod
    def get_user_last_match_type(db: Client, user_id: str) -> str:
        """Fetch the last match type recorded by the user."""
        doc = cast("DocumentSnapshot", db.collection("users").document(user_id).get())
        return (
            (doc.to_dict() or {}).get("lastMatchRecordedType", "singles")
            if doc.exists
            else "singles"
        )

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        """Fetch names for two teams."""
        t1 = cast("DocumentSnapshot", db.collection("teams").document(team1_id).get())
        t2 = cast("DocumentSnapshot", db.collection("teams").document(team2_id).get())
        return (
            (t1.to_dict() or {}).get("name", "Team 1") if t1.exists else "Team 1",
            (t2.to_dict() or {}).get("name", "Team 2") if t2.exists else "Team 2",
        )

    @staticmethod
    def get_match_edit_context(match_id: str) -> dict[str, Any] | None:
        """Fetch data needed for editing a match."""
        from firebase_admin import firestore

        db = firestore.client()
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if match_data is None:
            return None

        m_dict = cast("dict[str, Any]", match_data)
        match_type = m_dict.get("matchType", "singles")

        if match_type == "doubles":
            p1_name, p2_name = MatchQueryService._get_doubles_edit_names(db, m_dict)
        else:
            p1_name, p2_name = MatchQueryService._get_singles_edit_names(db, m_dict)

        return {
            "match": match_data,
            "player1_name": p1_name,
            "player2_name": p2_name,
        }

    @staticmethod
    def _get_doubles_edit_names(db: Client, m_dict: dict[str, Any]) -> tuple[str, str]:
        """Get player names for doubles match edit."""
        t1, t2 = m_dict.get("team1Id"), m_dict.get("team2Id")
        if t1 and t2:
            return MatchQueryService.get_team_names(db, t1, t2)
        return "Player 1", "Player 2"

    @staticmethod
    def _get_singles_edit_names(db: Client, m_dict: dict[str, Any]) -> tuple[str, str]:
        """Get player names for singles match edit."""
        p1_ref = m_dict.get("player1Ref")
        p2_ref = m_dict.get("player2Ref")
        uids = [ref.id for ref in [p1_ref, p2_ref] if ref]
        names = MatchQueryService.get_player_names(db, uids)

        p1_name = names.get(p1_ref.id, "Player 1") if p1_ref else "Player 1"
        p2_name = names.get(p2_ref.id, "Player 2") if p2_ref else "Player 2"
        return p1_name, p2_name
