"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES
from pickaladder.teams.services import TeamService
from pickaladder.user.services.core import get_avatar_url, smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user.models import UserSession

    from .models import Match, MatchResult, MatchSubmission


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
    ) -> tuple[float, float, float]:
        """Record a match and update stats using batched writes."""
        # 1. Read current snapshots (Optimized to 1 round-trip for reads)
        snapshots_iterable = db.get_all([p1_ref, p2_ref])
        snapshots_map = {snap.id: snap for snap in snapshots_iterable if snap.exists}

        p1_snapshot = cast("DocumentSnapshot", snapshots_map.get(p1_ref.id))
        p2_snapshot = cast("DocumentSnapshot", snapshots_map.get(p2_ref.id))

        p1_data = (
            cast(dict[str, Any], p1_snapshot.to_dict() or {}) if p1_snapshot else {}
        )
        p2_data = (
            cast(dict[str, Any], p2_snapshot.to_dict() or {}) if p2_snapshot else {}
        )

        # 1.5 Denormalize Player Data (Snapshots)
        if match_type == "singles":
            match_data["player_1_data"] = {
                "uid": p1_ref.id,
                "display_name": smart_display_name(p1_data or {}),
                "avatar_url": get_avatar_url(p1_data or {}),
                "dupr_at_match_time": float(
                    (p1_data or {}).get("duprRating")
                    or (p1_data or {}).get("dupr_rating")
                    or 0.0
                ),
            }
            match_data["player_2_data"] = {
                "uid": p2_ref.id,
                "display_name": smart_display_name(p2_data or {}),
                "avatar_url": get_avatar_url(p2_data or {}),
                "dupr_at_match_time": float(
                    (p2_data or {}).get("duprRating")
                    or (p2_data or {}).get("dupr_rating")
                    or 0.0
                ),
            }

        # 2. Calculate New Stats (Server-Side Authority)
        score1 = match_data["player1Score"]
        score2 = match_data["player2Score"]
        winner = "team1" if score1 > score2 else "team2"
        match_data["winner"] = winner

        match_data["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
        match_data["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id

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

        # Simple Elo Calculation (K=32)
        k = 32
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

        # Upset Logic (Singles only)
        if match_type == "singles":
            def get_rating(d: Any) -> float:
                val = d.get("dupr_rating") or d.get("duprRating")
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            p1_rating = get_rating(p1_data)
            p2_rating = get_rating(p2_data)

            if p1_rating > 0 and p2_rating > 0:
                if winner == "team1" and (p2_rating - p1_rating) >= UPSET_THRESHOLD:
                    match_data["is_upset"] = True
                elif winner == "team2" and (p1_rating - p2_rating) >= UPSET_THRESHOLD:
                    match_data["is_upset"] = True

        # 3. Queue Writes
        batch.set(match_ref, match_data)
        batch.update(p1_ref, p1_updates)
        batch.update(p2_ref, p2_updates)
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

        if group_id := match_data.get("groupId"):
            group_ref = db.collection("groups").document(group_id)
            batch.update(group_ref, {"updatedAt": firestore.SERVER_TIMESTAMP})

        return new_p1_elo, new_p2_elo, new_p1_elo - p1_elo

    @staticmethod
    def record_match(
        db: Client,
        submission: MatchSubmission,
        current_user: UserSession,
    ) -> MatchResult:
        """Process and record a match submission."""
        from .models import MatchResult

        user_id = current_user["uid"]
        user_ref = db.collection("users").document(user_id)

        # Helper to bridge field name differences and support both dict and object access
        def get_val(key_list: list[str]) -> Any:
            for k in key_list:
                if isinstance(submission, dict):
                    if k in submission:
                        return submission[k]
                elif hasattr(submission, k):
                    return getattr(submission, k)
            return None

        match_type = get_val(["match_type", "matchType"]) or "singles"
        p1_id = get_val(["player1", "player_1_id"])
        p2_id = get_val(["player2", "player_2_id"])
        partner_id = get_val(["partner", "partner_id"])
        opponent2_id = get_val(["opponent2", "opponent2_id", "opponent_2_id"])

        # Candidate Validation
        group_id = submission.group_id
        tournament_id = submission.tournament_id

        candidate_ids = MatchService.get_candidate_player_ids(
            db, user_id, group_id, tournament_id
        )
        player1_candidates = MatchService.get_candidate_player_ids(
            db, user_id, group_id, tournament_id, include_user=True
        )

        if p1_id not in player1_candidates:
            raise ValueError("Invalid Team 1 Player 1 selected.")
        if p2_id not in candidate_ids:
            raise ValueError("Invalid Opponent 1 selected.")
        if match_type == "doubles":
            if partner_id not in candidate_ids:
                raise ValueError("Invalid Partner selected.")
            if opponent2_id not in candidate_ids:
                raise ValueError("Invalid Opponent 2 selected.")

        # Determine Date
        match_date_input = submission.match_date
        if isinstance(match_date_input, str) and match_date_input:
            match_date = datetime.datetime.strptime(
                match_date_input, "%Y-%m-%d"
            ).replace(tzinfo=datetime.timezone.utc)
        elif isinstance(match_date_input, datetime.date) and not isinstance(
            match_date_input, datetime.datetime
        ):
            match_date = datetime.datetime.combine(
                match_date_input, datetime.time.min
            ).replace(tzinfo=datetime.timezone.utc)
        elif isinstance(match_date_input, datetime.datetime):
            match_date = match_date_input.replace(tzinfo=datetime.timezone.utc)
        else:
            match_date = datetime.datetime.now(datetime.timezone.utc)

        player1_score = get_val(["player1_score", "score_p1", "player1Score"]) or 0
        player2_score = get_val(["player2_score", "score_p2", "player2Score"]) or 0

        match_doc_data: dict[str, Any] = {
            "player1Score": player1_score,
            "player2Score": player2_score,
            "matchDate": match_date,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": match_type,
            "createdBy": user_id,
        }

        if group_id:
            match_doc_data["groupId"] = group_id
        if tournament_id:
            match_doc_data["tournamentId"] = tournament_id

        if match_type == "singles":
            p1_ref = db.collection("users").document(p1_id)
            p2_ref = db.collection("users").document(p2_id)
            match_doc_data["player1Ref"] = p1_ref
            match_doc_data["player2Ref"] = p2_ref
            match_doc_data["participants"] = [p1_id, p2_id]
            side1_ref = p1_ref
            side2_ref = p2_ref
        elif match_type == "doubles":
            res = MatchService._resolve_teams(
                db, p1_id, cast(str, partner_id), cast(str, p2_id), cast(str, opponent2_id)
            )
            match_doc_data.update(res)
            match_doc_data["participants"] = [p1_id, cast(str, partner_id), p2_id, cast(str, opponent2_id)]
            side1_ref = cast("DocumentReference", res.get("team1Ref"))
            side2_ref = cast("DocumentReference", res.get("team2Ref"))
        else:
            raise ValueError("Unsupported match type.")

        new_match_ref = cast("DocumentReference", db.collection("matches").document())
        batch = db.batch()
        new_p1_elo, new_p2_elo, elo_delta = MatchService._record_match_batch(
            db, batch, new_match_ref, cast("DocumentReference", side1_ref),
            cast("DocumentReference", side2_ref), cast("DocumentReference", user_ref),
            match_doc_data, match_type,
        )
        batch.commit()

        return MatchResult(
            id=new_match_ref.id,
            matchType=match_doc_data.get("matchType", match_type),
            player1Score=match_doc_data.get("player1Score", player1_score),
            player2Score=match_doc_data.get("player2Score", player2_score),
            matchDate=match_doc_data.get("matchDate", match_date),
            createdAt=match_doc_data.get("createdAt", firestore.SERVER_TIMESTAMP),
            createdBy=match_doc_data.get("createdBy", user_id),
            winner=match_doc_data.get("winner", ""),
            winnerId=match_doc_data.get("winnerId", ""),
            loserId=match_doc_data.get("loserId", ""),
            groupId=match_doc_data.get("groupId"),
            tournamentId=match_doc_data.get("tournamentId"),
            player1Ref=match_doc_data.get("player1Ref"),
            player2Ref=match_doc_data.get("player2Ref"),
            team1=match_doc_data.get("team1"),
            team2=match_doc_data.get("team2"),
            team1Id=match_doc_data.get("team1Id"),
            team2Id=match_doc_data.get("team2Id"),
            team1Ref=match_doc_data.get("team1Ref"),
            team2Ref=match_doc_data.get("team2Ref"),
            is_upset=match_doc_data.get("is_upset", False),
            match_doc=match_doc_data,
            player1_new_rating=new_p1_elo,
            player2_new_rating=new_p2_elo,
            rating_change=elo_delta,
        )

    @staticmethod
    def _resolve_teams(db: Client, t1_p1_id: str, t1_p2_id: str, t2_p1_id: str, t2_p2_id: str) -> dict[str, Any]:
        team1_id = TeamService.get_or_create_team(db, t1_p1_id, t1_p2_id)
        team2_id = TeamService.get_or_create_team(db, t2_p1_id, t2_p2_id)
        return {
            "team1": [db.collection("users").document(t1_p1_id), db.collection("users").document(t1_p2_id)],
            "team2": [db.collection("users").document(t2_p1_id), db.collection("users").document(t2_p2_id)],
            "team1Id": team1_id,
            "team2Id": team2_id,
            "team1Ref": db.collection("teams").document(team1_id),
            "team2Ref": db.collection("teams").document(team2_id),
        }

    @staticmethod
    def get_candidate_player_ids(db: Client, user_id: str, group_id: str | None = None, tournament_id: str | None = None, include_user: bool = False) -> set[str]:
        candidate_player_ids: set[str] = {user_id}
        if tournament_id:
            tournament = cast("DocumentSnapshot", db.collection("tournaments").document(tournament_id).get())
            if tournament.exists:
                candidate_player_ids.update((tournament.to_dict() or {}).get("participant_ids", []))
        elif group_id:
            group = cast("DocumentSnapshot", db.collection("groups").document(group_id).get())
            if group.exists:
                for ref in (group.to_dict() or {}).get("members", []):
                    candidate_player_ids.add(ref.id)
            invites = db.collection("group_invites").where(filter=firestore.FieldFilter("group_id", "==", group_id)).where(filter=firestore.FieldFilter("used", "==", False)).stream()
            invited_emails = [doc.to_dict().get("email") for doc in invites]
            if invited_emails:
                for i in range(0, len(invited_emails), 30):
                    users_by_email = db.collection("users").where(filter=firestore.FieldFilter("email", "in", invited_emails[i:i+30])).stream()
                    for u in users_by_email: candidate_player_ids.add(u.id)
        else:
            friends = db.collection("users").document(user_id).collection("friends").stream()
            for doc in friends:
                if doc.to_dict().get("status") in ["accepted", "pending"]: candidate_player_ids.add(doc.id)
        if not include_user: candidate_player_ids.discard(user_id)
        return candidate_player_ids

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        wins = losses = 0
        q1 = db.collection("matches").where(filter=firestore.FieldFilter("player1Ref", "==", player_ref)).stream()
        for m in q1:
            d = m.to_dict()
            if d.get("matchType") != "doubles":
                if d.get("player1Score", 0) > d.get("player2Score", 0): wins += 1
                else: losses += 1
        q2 = db.collection("matches").where(filter=firestore.FieldFilter("player2Ref", "==", player_ref)).stream()
        for m in q2:
            d = m.to_dict()
            if d.get("matchType") != "doubles":
                if d.get("player2Score", 0) > d.get("player1Score", 0): wins += 1
                else: losses += 1
        return {"wins": wins, "losses": losses}

    @staticmethod
    def get_match_by_id(db: Client, match_id: str) -> Match | None:
        doc = cast("DocumentSnapshot", db.collection("matches").document(match_id).get())
        if not doc.exists: return None
        data = cast("Match", doc.to_dict() or {}); data["id"] = match_id
        return data

    @staticmethod
    def get_leaderboard_data(db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES) -> list[Any]:
        users = db.collection("users").stream()
        players = []
        for u in users:
            d = u.to_dict() or {}; d["id"] = u.id
            rec = MatchService.get_player_record(db, db.collection("users").document(u.id))
            gp = rec["wins"] + rec["losses"]
            if gp >= min_games:
                d.update({"wins": rec["wins"], "losses": rec["losses"], "games_played": gp, "win_percentage": (rec["wins"]/gp)*100 if gp > 0 else 0})
                players.append(d)
        players.sort(key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True)
        return players[:limit]

    @staticmethod
    def update_match_score(db: Client, match_id: str, p1: int, p2: int, editor: str) -> None:
        ref = db.collection("matches").document(match_id)
        if not ref.get().exists: raise ValueError("Match not found.")
        ref.update({"player1Score": p1, "player2Score": p2, "winner": "team1" if p1 > p2 else "team2"})

    @staticmethod
    def get_matches_for_user(db: Client, uid: str, limit: int = 20, start_after: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
        from pickaladder.user.services.match_stats import format_matches_for_dashboard
        query = db.collection("matches").where(filter=firestore.FieldFilter("participants", "array_contains", uid)).order_by("matchDate", direction=firestore.Query.DESCENDING).limit(limit)
        if start_after:
            last = db.collection("matches").document(start_after).get()
            if last.exists: query = query.start_after(last)
        docs = list(query.stream())
        return (format_matches_for_dashboard(db, docs, uid), docs[-1].id) if docs else ([], None)

    @staticmethod
    def get_latest_matches(db: Client, limit: int = 10) -> list[Match]:
        docs = db.collection("matches").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit).stream()
        res = []
        for d in docs:
            m = cast("Match", d.to_dict() or {}); m["id"] = d.id; res.append(m)
        return res

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        names = {}
        for d in db.get_all([db.collection("users").document(u) for u in uids]):
            if d.exists: names[d.id] = (d.to_dict() or {}).get("name", d.id)
        return names

    @staticmethod
    def get_tournament_name(db: Client, tournament_id: str) -> str | None:
        doc = cast("DocumentSnapshot", db.collection("tournaments").document(tournament_id).get())
        return (doc.to_dict() or {}).get("name") if doc.exists else None

    @staticmethod
    def get_user_last_match_type(db: Client, user_id: str) -> str:
        doc = cast("DocumentSnapshot", db.collection("users").document(user_id).get())
        return (doc.to_dict() or {}).get("lastMatchRecordedType", "singles") if doc.exists else "singles"

    @staticmethod
    def get_team_names(db: Client, t1: str, t2: str) -> tuple[str, str]:
        d1, d2 = db.collection("teams").document(t1).get(), db.collection("teams").document(t2).get()
        return (d1.to_dict() or {}).get("name", "Team 1") if d1.exists else "Team 1", (d2.to_dict() or {}).get("name", "Team 2") if d2.exists else "Team 2"

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        match_data = MatchService.get_match_by_id(db, match_id)
        if not match_data: return {}
        m_dict = cast("dict[str, Any]", match_data)
        m_type = m_dict.get("matchType", "singles")
        context = {"match": match_data, "match_type": m_type}
        if m_type == "doubles":
            for side in ["team1", "team2"]:
                data = []
                for d in db.get_all(m_dict.get(side, [])):
                    if d.exists:
                        p = cast(dict[str, Any], d.to_dict() or {})
                        p["id"] = d.id; data.append(p)
                context[side] = data
        else:
            for p in ["player1", "player2"]:
                ref = m_dict.get(f"{p}Ref")
                if ref:
                    doc = cast("DocumentSnapshot", ref.get())
                    if doc.exists:
                        d = cast(dict[str, Any], doc.to_dict() or {})
                        d["id"] = doc.id
                        context[p] = d
                        context[f"{p}_record"] = MatchService.get_player_record(db, ref)
        return context