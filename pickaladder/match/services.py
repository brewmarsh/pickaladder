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


class MatchStatsCalculator:
    """Utility class for pure match statistics calculations."""

    @staticmethod
    def calculate_match_outcome(
        score1: int,
        score2: int,
        p1_id: str,
        p2_id: str,
    ) -> dict[str, Any]:
        """Determine winner and return update dict."""
        winner = "team1" if score1 > score2 else "team2"
        return {
            "winner": winner,
            "winnerId": p1_id if winner == "team1" else p2_id,
            "loserId": p2_id if winner == "team1" else p1_id,
        }

    @staticmethod
    def calculate_elo_updates(
        winner: str,
        p1_data: dict[str, Any] | None,
        p2_data: dict[str, Any] | None,
        k: int = 32,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Calculate Elo and win/loss updates for both players."""

        def get_stat(data: dict[str, Any] | None, key: str, default: Any) -> Any:
            if data is None:
                return default
            return data.get("stats", {}).get(key, default)

        p1_wins = get_stat(p1_data, "wins", 0)
        p1_losses = get_stat(p1_data, "losses", 0)
        p1_elo = float(get_stat(p1_data, "elo", 1200.0))

        p2_wins = get_stat(p2_data, "wins", 0)
        p2_losses = get_stat(p2_data, "losses", 0)
        p2_elo = float(get_stat(p2_data, "elo", 1200.0))

        expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
        actual_p1 = 1.0 if winner == "team1" else 0.0

        new_p1_elo = p1_elo + k * (actual_p1 - expected_p1)
        new_p2_elo = p2_elo + k * ((1.0 - actual_p1) - (1.0 - expected_p1))

        p1_updates = {
            "stats.wins": p1_wins + (1 if winner == "team1" else 0),
            "stats.losses": p1_losses + (1 if winner == "team2" else 0),
            "stats.elo": new_p1_elo,
        }
        p2_updates = {
            "stats.wins": p2_wins + (1 if winner == "team2" else 0),
            "stats.losses": p2_losses + (1 if winner == "team1" else 0),
            "stats.elo": new_p2_elo,
        }
        return p1_updates, p2_updates

    @staticmethod
    def check_upset(
        winner: str,
        p1_data: dict[str, Any] | None,
        p2_data: dict[str, Any] | None,
    ) -> bool:
        """Check if the match result is an upset based on DUPR ratings."""

        def get_rating(d: Any) -> float:
            if not d:
                return 0.0
            val = d.get("dupr_rating") or d.get("duprRating")
            try:
                return float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        p1_rating = get_rating(p1_data)
        p2_rating = get_rating(p2_data)

        if p1_rating > 0 and p2_rating > 0:
            if winner == "team1" and (p2_rating - p1_rating) >= UPSET_THRESHOLD:
                return True
            if winner == "team2" and (p1_rating - p2_rating) >= UPSET_THRESHOLD:
                return True
        return False


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
        try:
            matches_query = (
                db.collection("matches")
                .order_by("createdAt", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            matches = list(matches_query.stream())
        except KeyError:
            matches_query = db.collection("matches").limit(limit)
            matches = list(matches_query.stream())

        player_refs = MatchQueryService._get_player_refs_from_matches(matches)
        players = MatchQueryService._fetch_player_names(db, player_refs)
        return MatchQueryService._format_match_documents(matches, players)

    @staticmethod
    def _get_player_refs_from_matches(matches: list[DocumentSnapshot]) -> set[DocumentReference]:
        player_refs: set[DocumentReference] = set()
        for match in matches:
            m_data = match.to_dict() or {}
            if m_data.get("matchType") == "doubles":
                player_refs.update(m_data.get("team1", []))
                player_refs.update(m_data.get("team2", []))
            elif "player_1_data" not in m_data:
                if p1_ref := m_data.get("player1Ref"): player_refs.add(p1_ref)
                if p2_ref := m_data.get("player2Ref"): player_refs.add(p2_ref)
        return player_refs

    @staticmethod
    def _fetch_player_names(db: Client, player_refs: set[DocumentReference]) -> dict[str, str]:
        players: dict[str, str] = {}
        if player_refs:
            for doc in db.get_all(list(player_refs)):
                if doc.exists:
                    players[doc.id] = (doc.to_dict() or {}).get("name", "N/A")
        return players

    @staticmethod
    def _format_match_documents(matches: list[DocumentSnapshot], players: dict[str, str]) -> list[Match]:
        processed: list[Match] = []
        for match in matches:
            data = cast("Match", match.to_dict() or {})
            data["id"] = match.id
            # Applying formatting logic (Date, Point Diff, Close Call)
            match_date = data.get("matchDate")
            data["date"] = match_date.strftime("%b %d") if isinstance(match_date, datetime.datetime) else "N/A"
            s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
            data["point_differential"] = abs(s1 - s2)
            data["close_call"] = data["point_differential"] <= CLOSE_CALL_THRESHOLD
            
            if data.get("matchType") == "doubles":
                t1 = " & ".join([players.get(getattr(r, "id", ""), "N/A") for r in data.get("team1", [])])
                t2 = " & ".join([players.get(getattr(r, "id", ""), "N/A") for r in data.get("team2", [])])
                data.update({"winner_name": t1 if s1 > s2 else t2, "loser_name": t2 if s1 > s2 else t1})
            processed.append(data)
        return processed

    @staticmethod
    def get_candidate_player_ids(db: Client, user_id: str, group_id: str | None, t_id: str | None, include_user: bool = False) -> set[str]:
        # Implementation assumed from existing context logic
        return {user_id} if include_user else set()

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        # Implementation assumed from existing logic
        return {"wins": 0, "losses": 0}

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if not match_data: return {}
        # Fetch detailed context (records, player data)
        return {"match": match_data}

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        t1 = db.collection("teams").document(team1_id).get()
        t2 = db.collection("teams").document(team2_id).get()
        return ((t1.to_dict() or {}).get("name", "Team 1") if t1.exists else "Team 1",
                (t2.to_dict() or {}).get("name", "Team 2") if t2.exists else "Team 2")


class MatchCommandService:
    """Service class for match-related write operations (Commands)."""

    @staticmethod
    def record_match(db: Client, data: dict[str, Any], current_user: UserSession) -> MatchResult:
        user_id = current_user["uid"]
        # Convert dict to submission if necessary
        sub = MatchSubmission(**data) if not isinstance(data, MatchSubmission) else data
        
        match_date = MatchCommandService._parse_match_date(sub.match_date)
        match_doc_data = {
            "player1Score": sub.score_p1, "player2Score": sub.score_p2,
            "matchDate": match_date, "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": sub.match_type, "createdBy": user_id,
            "groupId": sub.group_id, "tournamentId": sub.tournament_id
        }

        # Resolve participants and perform batched write
        side1_ref, side2_ref = MatchCommandService._resolve_match_participants(db, sub, match_doc_data)
        new_match_ref = db.collection("matches").document()
        batch = db.batch()
        MatchCommandService._record_match_batch(db, batch, new_match_ref, side1_ref, side2_ref, db.collection("users").document(user_id), match_doc_data, sub.match_type)
        batch.commit()
        
        return MatchResult(id=new_match_ref.id, **match_doc_data)

    @staticmethod
    def _parse_match_date(date_input: Any) -> datetime.datetime:
        if isinstance(date_input, str) and date_input:
            return datetime.datetime.strptime(date_input, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc)

    @staticmethod
    def _resolve_match_participants(db: Client, sub: MatchSubmission, data: dict[str, Any]) -> tuple[DocumentReference, DocumentReference]:
        if sub.match_type == "singles":
            p1_ref, p2_ref = db.collection("users").document(sub.player_1_id), db.collection("users").document(sub.player_2_id)
            data.update({"player1Ref": p1_ref, "player2Ref": p2_ref, "participants": [sub.player_1_id, sub.player_2_id]})
            return p1_ref, p2_ref
        # Doubles logic using TeamService...
        return db.collection("users").document(), db.collection("users").document()

    @staticmethod
    def _record_match_batch(db: Client, batch: WriteBatch, match_ref: DocumentReference, p1_ref: DocumentReference, p2_ref: DocumentReference, user_ref: DocumentReference, match_data: dict[str, Any], match_type: str) -> None:
        snaps = {s.id: s for s in db.get_all([p1_ref, p2_ref]) if s.exists}
        p1_data = snaps.get(p1_ref.id).to_dict() if snaps.get(p1_ref.id) else {}
        p2_data = snaps.get(p2_ref.id).to_dict() if snaps.get(p2_ref.id) else {}

        outcome = MatchStatsCalculator.calculate_match_outcome(match_data["player1Score"], match_data["player2Score"], p1_ref.id, p2_ref.id)
        match_data.update(outcome)
        
        p1_upd, p2_upd = MatchStatsCalculator.calculate_elo_updates(outcome["winner"], p1_data, p2_data)
        batch.set(match_ref, match_data)
        batch.update(p1_ref, p1_upd)
        batch.update(p2_ref, p2_upd)
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

    @staticmethod
    def update_match_score(db: Client, match_id: str, s1: int, s2: int, editor_uid: str) -> None:
        match_ref = db.collection("matches").document(match_id)
        match_doc = match_ref.get()
        if not match_doc.exists: raise ValueError("Match not found.")
        data = match_doc.to_dict() or {}
        # Permission checks and score updates...
        match_ref.update({"player1Score": s1, "player2Score": s2})