from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES
from pickaladder.match.models import Match

from .formatting import MatchFormatter

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user.models import User

CLOSE_CALL_THRESHOLD = 2


class MatchQueryService:
    """Service class for match-related read operations."""

    @staticmethod
    def get_match_by_id(db: Client, match_id: str) -> Match | None:
        """Fetch a single match by its ID."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            return None
        data = cast("Match", match_doc.to_dict() or {})
        data["id"] = match_id
        return data

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
        match_data = cast("Match", match_doc.to_dict() or {})
        match_data["id"] = match_doc.id
        MatchFormatter.apply_common_match_formatting(match_data)

        player_refs = MatchQueryService._get_player_refs_from_matches([match_doc])
        players = MatchQueryService._fetch_player_names(db, player_refs)

        if match_data.get("matchType") == "doubles":
            MatchFormatter.format_doubles_match_names(match_data, players)
        else:
            MatchFormatter.format_singles_match_names(match_data, players)

        return match_data

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
        refs: set[DocumentReference] = set()
        if m_data.get("matchType") == "doubles":
            refs.update(m_data.get("team1", []))
            refs.update(m_data.get("team2", []))
        elif "player_1_data" not in m_data or "player_2_data" not in m_data:
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
    def get_candidate_player_ids(
        db: Client,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
        include_user: bool = False,
    ) -> set[str]:
        """Fetch a set of valid opponent IDs for a user."""
        candidate_ids: set[str] = {user_id}
        if tournament_id:
            candidate_ids.update(
                MatchQueryService._get_tournament_participants(db, tournament_id)
            )
        elif group_id:
            candidate_ids.update(MatchQueryService._get_group_candidates(db, group_id))
        else:
            candidate_ids.update(MatchQueryService._get_default_candidates(db, user_id))

        if not include_user:
            candidate_ids.discard(user_id)
        return candidate_ids

    @staticmethod
    def _get_tournament_participants(db: Client, tournament_id: str) -> list[str]:
        """Fetch participant IDs for a tournament."""
        doc = cast(
            "DocumentSnapshot",
            db.collection("tournaments").document(tournament_id).get(),
        )
        return (doc.to_dict() or {}).get("participant_ids", []) if doc.exists else []

    @staticmethod
    def _get_group_candidates(db: Client, group_id: str) -> set[str]:
        """Fetch group members and invited users for a group."""
        from firebase_admin import firestore

        candidates: set[str] = set()
        group_doc = cast(
            "DocumentSnapshot", db.collection("groups").document(group_id).get()
        )
        if group_doc.exists:
            for ref in (group_doc.to_dict() or {}).get("members", []):
                candidates.add(ref.id)

        invites = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("group_id", "==", group_id))
            .where(filter=firestore.FieldFilter("used", "==", False))
            .stream()
        )
        emails = [
            (doc.to_dict() or {}).get("email")
            for doc in invites
            if (doc.to_dict() or {}).get("email")
        ]
        if emails:
            for i in range(0, len(emails), 30):
                users = (
                    db.collection("users")
                    .where(
                        filter=firestore.FieldFilter("email", "in", emails[i : i + 30])
                    )
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates

    @staticmethod
    def _get_default_candidates(db: Client, user_id: str) -> set[str]:
        """Fetch friends and personal invitees for a user."""
        from firebase_admin import firestore

        candidates: set[str] = set()
        friends = (
            db.collection("users").document(user_id).collection("friends").stream()
        )
        candidates.update(
            f.id
            for f in friends
            if (f.to_dict() or {}).get("status") in ["accepted", "pending"]
        )

        invites = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
            .stream()
        )
        emails = list(
            {
                (doc.to_dict() or {}).get("email")
                for doc in invites
                if (doc.to_dict() or {}).get("email")
            }
        )
        if emails:
            for i in range(0, len(emails), 10):
                users = (
                    db.collection("users")
                    .where(
                        filter=firestore.FieldFilter("email", "in", emails[i : i + 10])
                    )
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference."""
        from firebase_admin import firestore

        wins, losses = 0, 0
        uid = (
            player_ref.id
            if player_ref is not None and hasattr(player_ref, "id")
            else str(player_ref)
        )

        query = db.collection("matches").where(
            filter=firestore.FieldFilter("participants", "array_contains", uid)
        )

        for match in query.stream():
            data = match.to_dict()
            if not data:
                continue

            s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
            if s1 == s2:
                continue

            is_team1 = MatchQueryService._is_user_on_team1(data, uid)
            if (is_team1 and s1 > s2) or (not is_team1 and s2 > s1):
                wins += 1
            else:
                losses += 1

        return {"wins": wins, "losses": losses}

    @staticmethod
    def _is_user_on_team1(data: dict[str, Any], uid: str) -> bool:
        """Determine if a user is on the Team 1 side of a match."""
        if data.get("matchType") == "doubles":
            team1_refs = data.get("team1", [])
            return any(
                (r.id if r is not None and hasattr(r, "id") else "") == uid
                for r in team1_refs
            )
        p1_ref = data.get("player1Ref")
        return (
            p1_ref.id if p1_ref is not None and hasattr(p1_ref, "id") else ""
        ) == uid

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data needed for the match summary view."""
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if not match_data:
            return {}

        match_type = cast(dict[str, Any], match_data).get("matchType", "singles")
        context = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            context.update(
                MatchQueryService._get_doubles_summary_context(db, match_data)
            )
        else:
            context.update(
                MatchQueryService._get_singles_summary_context(db, match_data)
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
                    record = MatchQueryService.get_player_record(db, ref)
            res[key] = data
            res[f"{key}_record"] = record
        return res

    @staticmethod
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
        """Fetch data for the global leaderboard."""
        players: list[User] = []
        for u_snap in db.collection("users").stream():
            user_data = cast("User", u_snap.to_dict() or {})
            user_data["id"] = u_snap.id
            record = MatchQueryService.get_player_record(
                db, db.collection("users").document(u_snap.id)
            )

            games = record["wins"] + record["losses"]
            if games >= min_games:
                user_data.update(
                    {
                        "wins": record["wins"],
                        "losses": record["losses"],
                        "games_played": games,
                        "win_percentage": float((record["wins"] / games) * 100)
                        if games > 0
                        else 0.0,
                    }
                )
                players.append(user_data)

        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True
        )
        return players[:limit]

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
        player1_name = "Player 1"
        player2_name = "Player 2"

        if match_type == "doubles":
            t1, t2 = m_dict.get("team1Id"), m_dict.get("team2Id")
            if t1 and t2:
                player1_name, player2_name = MatchQueryService.get_team_names(
                    db, t1, t2
                )
        else:
            p1_ref = m_dict.get("player1Ref")
            p2_ref = m_dict.get("player2Ref")
            uids = [ref.id for ref in [p1_ref, p2_ref] if ref]
            names = MatchQueryService.get_player_names(db, uids)
            if p1_ref:
                player1_name = names.get(p1_ref.id, "Player 1")
            if p2_ref:
                player2_name = names.get(p2_ref.id, "Player 2")

        return {
            "match": match_data,
            "player1_name": player1_name,
            "player2_name": player2_name,
        }
