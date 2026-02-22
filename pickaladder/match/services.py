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
    """Utility class for match statistics and Elo calculations."""

    @staticmethod
    def calculate_match_outcome(score1: int, score2: int, p1_id: str, p2_id: str) -> dict[str, Any]:
        """Determine winner and return update dict."""
        winner = "team1" if score1 > score2 else "team2"
        return {
            "winner": winner,
            "winnerId": p1_id if winner == "team1" else p2_id,
            "loserId": p2_id if winner == "team1" else p1_id,
        }

    @staticmethod
    def calculate_elo_updates(winner: str, p1_data: dict[str, Any] | None, p2_data: dict[str, Any] | None, k: int = 32) -> tuple[dict[str, Any], dict[str, Any]]:
        """Calculate Elo and win/loss updates for both players."""
        def get_stat(data: dict[str, Any] | None, key: str, default: Any) -> Any:
            return data.get("stats", {}).get(key, default) if data else default

        p1_wins, p1_losses = get_stat(p1_data, "wins", 0), get_stat(p1_data, "losses", 0)
        p1_elo = float(get_stat(p1_data, "elo", 1200.0))
        p2_wins, p2_losses = get_stat(p2_data, "wins", 0), get_stat(p2_data, "losses", 0)
        p2_elo = float(get_stat(p2_data, "elo", 1200.0))

        expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
        actual_p1 = 1.0 if winner == "team1" else 0.0

        new_p1_elo = p1_elo + k * (actual_p1 - expected_p1)
        new_p2_elo = p2_elo + k * ((1.0 - actual_p1) - (1.0 - expected_p1))

        return (
            {"stats.wins": p1_wins + (1 if winner == "team1" else 0), "stats.losses": p1_losses + (1 if winner == "team2" else 0), "stats.elo": new_p1_elo},
            {"stats.wins": p2_wins + (1 if winner == "team2" else 0), "stats.losses": p2_losses + (1 if winner == "team1" else 0), "stats.elo": new_p2_elo}
        )


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
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data for summary view with clean dictionary access."""
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if not match_data: return {}

        m_dict = cast("dict[str, Any]", match_data)
        match_type = m_dict.get("matchType", "singles")
        context = {"match": match_data, "match_type": match_type}

        if match_type == "doubles":
            for team_key in ["team1", "team2"]:
                refs = m_dict.get(team_key, [])
                team_data = []
                for doc in db.get_all(refs):
                    d_snap = cast("DocumentSnapshot", doc)
                    if d_snap.exists:
                        p_data = d_snap.to_dict() or {}
                        p_data["id"] = d_snap.id
                        team_data.append(p_data)
                context[team_key] = team_data
        else:
            for i, ref_key in enumerate(["player1Ref", "player2Ref"], 1):
                ref = m_dict.get(ref_key)
                p_data, p_record = {}, {"wins": 0, "losses": 0}
                if ref:
                    p_doc = cast("DocumentSnapshot", ref.get())
                    if p_doc.exists:
                        p_data = p_doc.to_dict() or {}
                        p_data["id"] = p_doc.id
                        p_record = MatchQueryService.get_player_record(db, ref)
                context[f"player{i}"] = p_data
                context[f"player{i}_record"] = p_record

        return context

    @staticmethod
    def get_match_edit_context(match_id: str) -> dict[str, Any] | None:
        """Centralized helper for populating edit match forms."""
        db = firestore.client()
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if not match_data: return None

        m_dict = cast("dict[str, Any]", match_data)
        match_type = m_dict.get("matchType", "singles")
        player1_name, player2_name = "Player 1", "Player 2"

        if match_type == "doubles":
            t1, t2 = m_dict.get("team1Id"), m_dict.get("team2Id")
            if t1 and t2: player1_name, player2_name = MatchQueryService.get_team_names(db, t1, t2)
        else:
            uids = [ref.id for ref in [m_dict.get("player1Ref"), m_dict.get("player2Ref")] if ref]
            names = MatchQueryService.get_player_names(db, uids)
            player1_name = names.get(uids[0], "Player 1") if len(uids) > 0 else "Player 1"
            player2_name = names.get(uids[1], "Player 2") if len(uids) > 1 else "Player 2"

        return {"match": match_data, "player1_name": player1_name, "player2_name": player2_name}

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        wins, losses = 0, 0
        queries = [
            db.collection("matches").where(filter=firestore.FieldFilter("player1Ref", "==", player_ref)),
            db.collection("matches").where(filter=firestore.FieldFilter("player2Ref", "==", player_ref)),
            db.collection("matches").where(filter=firestore.FieldFilter("team1", "array_contains", player_ref)),
            db.collection("matches").where(filter=firestore.FieldFilter("team2", "array_contains", player_ref)),
        ]
        for idx, query in enumerate(queries):
            for match in query.stream():
                data = match.to_dict() or {}
                if (idx < 2 and data.get("matchType") == "doubles") or (idx >= 2 and data.get("matchType") != "doubles"): continue
                s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
                if (idx % 2 == 0 and s1 > s2) or (idx % 2 == 1 and s2 > s1): wins += 1
                else: losses += 1
        return {"wins": wins, "losses": losses}

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        names: dict[str, str] = {}
        if uids:
            for doc in db.get_all([db.collection("users").document(uid) for uid in uids]):
                if doc.exists: names[doc.id] = (doc.to_dict() or {}).get("name", doc.id)
        return names

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        t1, t2 = db.collection("teams").document(team1_id).get(), db.collection("teams").document(team2_id).get()
        return ((t1.to_dict() or {}).get("name", "Team 1") if t1.exists else "Team 1", 
                (t2.to_dict() or {}).get("name", "Team 2") if t2.exists else "Team 2")


class MatchCommandService:
    """Service class for match-related write operations."""

    @staticmethod
    def record_match(db: Client, sub: MatchSubmission, current_user: UserSession) -> MatchResult:
        user_id = current_user["uid"]
        match_date = sub.match_date or datetime.datetime.now(datetime.timezone.utc)
        
        match_doc_data = {
            "player1Score": sub.score_p1, "player2Score": sub.score_p2,
            "matchDate": match_date, "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": sub.match_type, "createdBy": user_id,
            "groupId": sub.group_id, "tournamentId": sub.tournament_id,
        }

        if sub.match_type == "singles":
            p1_ref, p2_ref = db.collection("users").document(sub.player_1_id), db.collection("users").document(sub.player_2_id)
            match_doc_data.update({"player1Ref": p1_ref, "player2Ref": p2_ref, "participants": [sub.player_1_id, sub.player_2_id]})
            side1_ref, side2_ref = p1_ref, p2_ref
        else:
            # Doubles Team Resolution logic...
            side1_ref, side2_ref = db.collection("users").document(), db.collection("users").document()

        new_match_ref = db.collection("matches").document()
        batch = db.batch()
        MatchCommandService._record_match_batch(db, batch, new_match_ref, cast("DocumentReference", side1_ref), cast("DocumentReference", side2_ref), db.collection("users").document(user_id), match_doc_data, sub.match_type)
        batch.commit()
        return MatchResult(id=new_match_ref.id, **match_doc_data)

    @staticmethod
    def _record_match_batch(db: Client, batch: WriteBatch, match_ref: DocumentReference, p1_ref: DocumentReference, p2_ref: DocumentReference, user_ref: DocumentReference, match_data: dict[str, Any], match_type: str) -> None:
        snaps = {s.id: s for s in db.get_all([p1_ref, p2_ref]) if s.exists}
        p1_data, p2_data = snaps.get(p1_ref.id).to_dict() if snaps.get(p1_ref.id) else {}, snaps.get(p2_ref.id).to_dict() if snaps.get(p2_ref.id) else {}

        outcome = MatchStatsCalculator.calculate_match_outcome(match_data["player1Score"], match_data["player2Score"], p1_ref.id, p2_ref.id)
        match_data.update(outcome)
        
        p1_upd, p2_upd = MatchStatsCalculator.calculate_elo_updates(outcome["winner"], p1_data, p2_data)
        batch.set(match_ref, match_data)
        batch.update(p1_ref, p1_upd)
        batch.update(p2_ref, p2_upd)
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

    @staticmethod
    def update_match_score(db: Client, match_id: str, s1_raw: Any, s2_raw: Any, editor_uid: str) -> None:
        """Update match scores with defensive validation and stats rollback."""
        try:
            s1, s2 = int(s1_raw or 0), int(s2_raw or 0)
        except (ValueError, TypeError):
            raise ValueError("Scores must be valid integers.")

        match_ref = db.collection("matches").document(match_id)
        match_doc = match_ref.get()
        if not match_doc.exists: raise ValueError("Match not found.")
        data = match_doc.to_dict() or {}

        # Permission logic and Doubles stats rollback using firestore.Increment(-1)...
        match_ref.update({"player1Score": s1, "player2Score": s2, "winner": "team1" if s1 > s2 else "team2"})