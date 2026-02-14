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

        p1_snapshot = snapshots_map.get(p1_ref.id)
        p2_snapshot = snapshots_map.get(p2_ref.id)

        p1_data: dict[str, Any] = (
            cast("DocumentSnapshot", p1_snapshot).to_dict() if p1_snapshot else {}
        ) or {}
        p2_data: dict[str, Any] = (
            cast("DocumentSnapshot", p2_snapshot).to_dict() if p2_snapshot else {}
        ) or {}

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

        # Set winnerId and loserId based on match type
        if match_type == "singles":
            match_data["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
            match_data["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id
        else:
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

        # Update the Group timestamp
        if group_id := match_data.get("groupId"):
            group_ref = db.collection("groups").document(group_id)
            batch.update(group_ref, {"updatedAt": firestore.SERVER_TIMESTAMP})

    @staticmethod
    def record_match(
        db: Client,
        submission: MatchSubmission,
        current_user: UserSession,
    ) -> MatchResult:
        """Process and record a match submission."""
        user_id = current_user["uid"]
        user_ref = db.collection("users").document(user_id)

        match_type = submission.match_type
        p1_id = submission.player_1_id
        p2_id = submission.player_2_id
        partner_id = submission.partner_id
        opponent2_id = submission.opponent_2_id

        # Validation
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

        # Date Parsing
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

        player1_score = submission.score_p1
        player2_score = submission.score_p2

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
                db,
                p1_id,
                cast(str, partner_id),
                cast(str, p2_id),
                cast(str, opponent2_id),
            )
            match_doc_data.update(res)
            match_doc_data["participants"] = [
                p1_id,
                cast(str, partner_id),
                p2_id,
                cast(str, opponent2_id),
            ]
            side1_ref = cast("DocumentReference", res.get("team1Ref"))
            side2_ref = cast("DocumentReference", res.get("team2Ref"))
        else:
            raise ValueError("Unsupported match type.")

        # Save via batch
        new_match_ref = cast("DocumentReference", db.collection("matches").document())
        batch = db.batch()
        MatchService._record_match_batch(
            db,
            batch,
            new_match_ref,
            cast("DocumentReference", side1_ref),
            cast("DocumentReference", side2_ref),
            cast("DocumentReference", user_ref),
            match_doc_data,
            match_type,
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
        )

    @staticmethod
    def _resolve_teams(
        db: Client,
        t1_p1_id: str,
        t1_p2_id: str,
        t2_p1_id: str,
        t2_p2_id: str,
    ) -> dict[str, Any]:
        """Resolve and create/fetch teams for doubles matches."""
        team1_id = TeamService.get_or_create_team(db, t1_p1_id, t1_p2_id)
        team2_id = TeamService.get_or_create_team(db, t2_p1_id, t2_p2_id)

        t1_p1_ref = db.collection("users").document(t1_p1_id)
        t1_p2_ref = db.collection("users").document(t1_p2_id)
        t2_p1_ref = db.collection("users").document(t2_p1_id)
        t2_p2_ref = db.collection("users").document(t2_p2_id)

        team1_ref = db.collection("teams").document(team1_id)
        team2_ref = db.collection("teams").document(team2_id)

        return {
            "team1": [t1_p1_ref, t1_p2_ref],
            "team2": [t2_p1_ref, t2_p2_ref],
            "team1Id": team1_id,
            "team2Id": team2_id,
            "team1Ref": team1_ref,
            "team2Ref": team2_ref,
        }

    @staticmethod
    def get_candidate_player_ids(
        db: Client,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
        include_user: bool = False,
    ) -> set[str]:
        """Fetch a set of valid opponent IDs for a user."""
        candidate_player_ids: set[str] = {user_id}

        if tournament_id:
            tournament_ref = db.collection("tournaments").document(tournament_id)
            tournament = cast("DocumentSnapshot", tournament_ref.get())
            if tournament.exists:
                t_data = tournament.to_dict() or {}
                participant_ids = t_data.get("participant_ids", [])
                candidate_player_ids.update(participant_ids)
        elif group_id:
            group_ref = db.collection("groups").document(group_id)
            group = cast("DocumentSnapshot", group_ref.get())
            if group.exists:
                group_data = group.to_dict() or {}
                member_refs = group_data.get("members", [])
                for ref in member_refs:
                    candidate_player_ids.add(ref.id)

            invites_query = (
                db.collection("group_invites")
                .where(filter=firestore.FieldFilter("group_id", "==", group_id))
                .where(filter=firestore.FieldFilter("used", "==", False))
                .stream()
            )
            invited_emails = [
                (doc.to_dict() or {}).get("email") for doc in invites_query
            ]

            if invited_emails:
                for i in range(0, len(invited_emails), 30):
                    batch_emails = invited_emails[i : i + 30]
                    users_by_email = (
                        db.collection("users")
                        .where(
                            filter=firestore.FieldFilter("email", "in", batch_emails)
                        )
                        .stream()
                    )
                    for user_doc in users_by_email:
                        candidate_player_ids.add(user_doc.id)
        else:
            friends_ref = db.collection("users").document(user_id).collection("friends")
            friends_docs = friends_ref.stream()
            for doc in friends_docs:
                if doc.to_dict().get("status") in ["accepted", "pending"]:
                    candidate_player_ids.add(doc.id)

        if not include_user:
            candidate_player_ids.discard(user_id)
        return candidate_player_ids

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference."""
        wins = 0
        losses = 0

        # Singles as p1
        p1_matches = db.collection("matches").where(filter=firestore.FieldFilter("player1Ref", "==", player_ref)).stream()
        for match in p1_matches:
            data = match.to_dict()
            if data and data.get("matchType") != "doubles":
                if data.get("player1Score", 0) > data.get("player2Score", 0):
                    wins += 1
                else:
                    losses += 1

        # Singles as p2
        p2_matches = db.collection("matches").where(filter=firestore.FieldFilter("player2Ref", "==", player_ref)).stream()
        for match in p2_matches:
            data = match.to_dict()
            if data and data.get("matchType") != "doubles":
                if data.get("player2Score", 0) > data.get("player1Score", 0):
                    wins += 1
                else:
                    losses += 1

        # Doubles as team 1
        t1_matches = db.collection("matches").where(filter=firestore.FieldFilter("team1", "array_contains", player_ref)).stream()
        for match in t1_matches:
            data = match.to_dict()
            if data and data.get("matchType") == "doubles":
                if data.get("player1Score", 0) > data.get("player2Score", 0):
                    wins += 1
                else:
                    losses += 1

        # Doubles as team 2
        t2_matches = db.collection("matches").where(filter=firestore.FieldFilter("team2", "array_contains", player_ref)).stream()
        for match in t2_matches:
            data = match.to_dict()
            if data and data.get("matchType") == "doubles":
                if data.get("player2Score", 0) > data.get("player1Score", 0):
                    wins += 1
                else:
                    losses += 1

        return {"wins": wins, "losses": losses}

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
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
        """Fetch data for the global leaderboard."""
        users_query = db.collection("users").stream()
        players: list[User] = []
        for user in users_query:
            u_snap = cast("DocumentSnapshot", user)
            user_data = cast("User", u_snap.to_dict() or {})
            user_data["id"] = u_snap.id
            user_ref = db.collection("users").document(u_snap.id)
            record = MatchService.get_player_record(db, user_ref)

            win_percentage = 0.0
            games_played = record["wins"] + record["losses"]
            if games_played > 0:
                win_percentage = float((record["wins"] / games_played) * 100)

            user_data.update({
                "wins": record["wins"],
                "losses": record["losses"],
                "games_played": games_played,
                "win_percentage": win_percentage
            })

            if games_played >= min_games:
                players.append(user_data)

        players.sort(key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True)
        return players[:limit]

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
            team1_refs = m_dict.get("team1", [])
            team2_refs = m_dict.get("team2", [])

            team1_data = []
            if team1_refs:
                for doc in db.get_all(team1_refs):
                    d_snap = cast("DocumentSnapshot", doc)
                    if d_snap.exists:
                        p_dict = cast(dict[str, Any], d_snap.to_dict() or {})
                        p_data = {**p_dict, "id": d_snap.id}
                        team1_data.append(p_data)

            team2_data = []
            if team2_refs:
                for doc in db.get_all(team2_refs):
                    d_snap = cast("DocumentSnapshot", doc)
                    if d_snap.exists:
                        p_dict = cast(dict[str, Any], d_snap.to_dict() or {})
                        p_data = {**p_dict, "id": d_snap.id}
                        team2_data.append(p_data)

            context["team1"] = team1_data
            context["team2"] = team2_data
        else:
            player1_ref = m_dict.get("player1Ref")
            player2_ref = m_dict.get("player2Ref")

            player1_data = {}
            player2_data = {}
            player1_record = {"wins": 0, "losses": 0}
            player2_record = {"wins": 0, "losses": 0}

            if player1_ref:
                p1_doc = cast("DocumentSnapshot", player1_ref.get())
                if p1_doc.exists:
                    p1_dict = cast(dict[str, Any], p1_doc.to_dict() or {})
                    player1_data = {**p1_dict, "id": p1_doc.id}
                    player1_record = MatchService.get_player_record(db, player1_ref)

            if player2_ref:
                p2_doc = cast("DocumentSnapshot", player2_ref.get())
                if p2_doc.exists:
                    p2_dict = cast(dict[str, Any], p2_doc.to_dict() or {})
                    player2_data = {**p2_dict, "id": p2_doc.id}
                    player2_record = MatchService.get_player_record(db, player2_ref)

            context.update({
                "player1": player1_data,
                "player2": player2_data,
                "player1_record": player1_record,
                "player2_record": player2_record,
            })

        return context

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        """Fetch a mapping of UIDs to names."""
        names: dict[str, str] = {}
        if not uids:
            return names
        u_refs = [db.collection("users").document(uid) for uid in uids]
        for doc in db.get_all(u_refs):
            if cast("DocumentSnapshot", doc).exists:
                d = cast("DocumentSnapshot", doc).to_dict() or {}
                names[str(doc.id)] = d.get("name", doc.id)
        return names

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        """Fetch names for two teams."""
        t1_doc = cast("DocumentSnapshot", db.collection("teams").document(team1_id).get())
        t2_doc = cast("DocumentSnapshot", db.collection("teams").document(team2_id).get())

        name1 = cast(str, (t1_doc.to_dict() or {}).get("name", "Team 1")) if t1_doc.exists else "Team 1"
        name2 = cast(str, (t2_doc.to_dict() or {}).get("name", "Team 2")) if t2_doc.exists else "Team 2"
        return name1, name2