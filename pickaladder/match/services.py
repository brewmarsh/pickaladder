"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES
from pickaladder.teams.services import TeamService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

    from pickaladder.user import User
    from pickaladder.user.models import UserSession

    from .models import Match


CLOSE_CALL_THRESHOLD = 2
UPSET_THRESHOLD = 0.25


class MatchService:
    """Service class for match-related operations."""

    @staticmethod
    def process_match_submission(
        db: Client,
        form_data: dict[str, Any],
        current_user: UserSession,
    ) -> str:
        """Process and record a match submission."""
        user_id = current_user["uid"]
        user_ref = db.collection("users").document(user_id)

        match_type = form_data.get("match_type") or "singles"
        p1_id = form_data.get("player1") or user_id
        p2_id = form_data.get("player2")
        partner_id = form_data.get("partner")
        opponent2_id = form_data.get("opponent2")

        # Uniqueness check
        player_ids = [p1_id, p2_id]
        if match_type == "doubles":
            player_ids.extend([partner_id, opponent2_id])

        active_players = [p for p in player_ids if p]
        if len(active_players) != len(set(active_players)):
            raise ValueError("All players must be unique.")

        # Candidate Validation
        group_id = form_data.get("group_id")
        tournament_id = form_data.get("tournament_id")

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
        match_date_input = form_data.get("match_date")
        if isinstance(match_date_input, str) and match_date_input:
            match_date = datetime.datetime.strptime(
                match_date_input, "%Y-%m-%d"
            ).replace(tzinfo=datetime.timezone.utc)
        elif isinstance(match_date_input, datetime.date):
            match_date = datetime.datetime.combine(
                match_date_input, datetime.time.min
            ).replace(tzinfo=datetime.timezone.utc)
        else:
            match_date = datetime.datetime.now(datetime.timezone.utc)

        player1_score = int(form_data.get("player1_score") or 0)
        player2_score = int(form_data.get("player2_score") or 0)

        match_doc_data: dict[str, Any] = {
            "player1Score": player1_score,
            "player2Score": player2_score,
            "matchDate": match_date,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": match_type,
        }

        # Add IDs if present
        if group_id:
            match_doc_data["groupId"] = group_id
        if tournament_id:
            match_doc_data["tournamentId"] = tournament_id

        team1_ref = None
        team2_ref = None

        if match_type == "singles":
            p1_ref = db.collection("users").document(p1_id)
            p2_ref = db.collection("users").document(p2_id)
            match_doc_data["player1Ref"] = p1_ref
            match_doc_data["player2Ref"] = p2_ref
            match_doc_data["winner"] = (
                "team1" if player1_score > player2_score else "team2"
            )

            # Apply DUPR upset logic
            MatchService._apply_upset_logic(match_doc_data, p1_ref, p2_ref)

        elif match_type == "doubles":
            res = MatchService._resolve_teams(
                db, p1_id, cast(str, partner_id), p2_id, cast(str, opponent2_id)
            )
            match_doc_data.update(res)
            team1_ref = res.get("team1Ref")
            team2_ref = res.get("team2Ref")
            match_doc_data["winner"] = (
                "team1" if player1_score > player2_score else "team2"
            )

        # Save to database
        new_match_ref = db.collection("matches").document()
        new_match_ref.set(match_doc_data)

        # Update stats
        MatchService._update_player_stats(
            user_ref, match_type, player1_score, player2_score, team1_ref, team2_ref
        )

        return new_match_ref.id

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
    def _update_player_stats(  # noqa: PLR0913
        user_ref: Any,
        match_type: str,
        player1_score: int,
        player2_score: int,
        team1_ref: Any = None,
        team2_ref: Any = None,
    ) -> None:
        """Update wins/losses and user's last match type."""
        if match_type == "doubles" and team1_ref and team2_ref:
            if player1_score > player2_score:
                team1_ref.update({"stats.wins": firestore.Increment(1)})
                team2_ref.update({"stats.losses": firestore.Increment(1)})
            elif player2_score > player1_score:
                team1_ref.update({"stats.losses": firestore.Increment(1)})
                team2_ref.update({"stats.wins": firestore.Increment(1)})

        user_ref.update({"lastMatchRecordedType": match_type})

    @staticmethod
    def _apply_upset_logic(
        match_data: dict[str, Any], p1_ref: Any, p2_ref: Any
    ) -> None:
        """Calculate if match is an upset based on DUPR and update match_data."""
        try:
            p1_doc = p1_ref.get()
            p2_doc = p2_ref.get()

            if not p1_doc.exists or not p2_doc.exists:
                return

            p1_data = p1_doc.to_dict() or {}
            p2_data = p2_doc.to_dict() or {}

            # Handle multiple possible DUPR rating keys, ensuring safety with mocks
            def get_rating(d: Any) -> float:
                val = d.get("dupr_rating") or d.get("duprRating")
                try:
                    return float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    return 0.0

            p1_rating = get_rating(p1_data)
            p2_rating = get_rating(p2_data)

            if p1_rating > 0 and p2_rating > 0:
                winner = match_data.get("winner")
                if winner == "team1" and (p2_rating - p1_rating) >= UPSET_THRESHOLD:
                    match_data["is_upset"] = True
                elif winner == "team2" and (p1_rating - p2_rating) >= UPSET_THRESHOLD:
                    match_data["is_upset"] = True
        except Exception as e:
            # Ensure upset logic failure doesn't block match recording
            logging.error(f"Error applying upset logic: {e}")

    @staticmethod
    def get_candidate_player_ids(
        db: Client,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
        include_user: bool = False,
    ) -> set[str]:
        """Fetch a set of valid opponent IDs for a user.

        Optionally restricts to a group or tournament.
        """
        candidate_player_ids: set[str] = {user_id}

        if tournament_id:
            # If in a tournament context, candidates are tournament participants
            tournament_ref = db.collection("tournaments").document(tournament_id)
            tournament = cast("DocumentSnapshot", tournament_ref.get())
            if tournament.exists:
                t_data = tournament.to_dict() or {}
                participant_ids = t_data.get("participant_ids", [])
                candidate_player_ids.update(participant_ids)
        elif group_id:
            # If in a group context, candidates are group members and pending invitees
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
            # If not in a group context, candidates are friends and user's own invitees
            friends_ref = db.collection("users").document(user_id).collection("friends")
            friends_docs = friends_ref.stream()
            for doc in friends_docs:
                if doc.to_dict().get("status") in ["accepted", "pending"]:
                    candidate_player_ids.add(doc.id)

            my_invites_query = (
                db.collection("group_invites")
                .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
                .stream()
            )
            my_invited_emails = {
                (doc.to_dict() or {}).get("email") for doc in my_invites_query
            }

            if my_invited_emails:
                my_invited_emails_list = list(my_invited_emails)
                for i in range(0, len(my_invited_emails_list), 10):
                    batch_emails = my_invited_emails_list[i : i + 10]
                    users_by_email = (
                        db.collection("users")
                        .where(
                            filter=firestore.FieldFilter("email", "in", batch_emails)
                        )
                        .stream()
                    )
                    for user_doc in users_by_email:
                        candidate_player_ids.add(user_doc.id)

        if not include_user:
            candidate_player_ids.discard(user_id)
        return candidate_player_ids

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference."""
        wins = 0
        losses = 0

        # 1. Matches where the user is player1 (Singles)
        p1_matches_query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", player_ref))
            .stream()
        )
        for match in p1_matches_query:
            data = match.to_dict()
            if not data or data.get("matchType") == "doubles":
                continue

            if data.get("player1Score", 0) > data.get("player2Score", 0):
                wins += 1
            else:
                losses += 1

        # 2. Matches where the user is player2 (Singles)
        p2_matches_query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", player_ref))
            .stream()
        )
        for match in p2_matches_query:
            data = match.to_dict()
            if not data or data.get("matchType") == "doubles":
                continue

            if data.get("player2Score", 0) > data.get("player1Score", 0):
                wins += 1
            else:
                losses += 1

        # 3. Matches where the user is in team1 (Doubles)
        t1_matches_query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", player_ref))
            .stream()
        )
        for match in t1_matches_query:
            data = match.to_dict()
            if not data or data.get("matchType") != "doubles":
                continue

            if data.get("player1Score", 0) > data.get("player2Score", 0):
                wins += 1
            else:
                losses += 1

        # 4. Matches where the user is in team2 (Doubles)
        t2_matches_query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", player_ref))
            .stream()
        )
        for match in t2_matches_query:
            data = match.to_dict()
            if not data or data.get("matchType") != "doubles":
                continue

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
    def get_leaderboard_data(db: Client, limit: int = 50) -> list[User]:
        """Fetch data for the global leaderboard."""
        # Removing limit from query to ensure we can find top players from whole base
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

            user_data["wins"] = record["wins"]
            user_data["losses"] = record["losses"]
            user_data["games_played"] = games_played
            user_data["win_percentage"] = win_percentage

            # Only include players with more than 4 games played to ensure
            # a representative leaderboard and filter inactive players.
            if games_played >= GLOBAL_LEADERBOARD_MIN_GAMES:
                players.append(user_data)

        # Sort players by win percentage, then by games played
        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("games_played", 0)),
            reverse=True,
        )
        return players[:limit]

    @staticmethod
    def get_latest_matches(db: Client, limit: int = 10) -> list[Match]:
        """Fetch and process the latest matches."""
        matches_query = (
            db.collection("matches")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        matches = list(matches_query.stream())

        player_refs = set()
        for match in matches:
            m_snap = cast("DocumentSnapshot", match)
            m_data = m_snap.to_dict()
            if not m_data:
                continue
            if m_data.get("matchType") == "doubles":
                player_refs.update(m_data.get("team1", []))
                player_refs.update(m_data.get("team2", []))
            else:
                if p1_ref := m_data.get("player1Ref"):
                    player_refs.add(p1_ref)
                if p2_ref := m_data.get("player2Ref"):
                    player_refs.add(p2_ref)

        players = {}
        if player_refs:
            player_docs = db.get_all(list(player_refs))
            for doc in player_docs:
                d_snap = cast("DocumentSnapshot", doc)
                if d_snap.exists:
                    d_data = d_snap.to_dict() or {}
                    players[d_snap.id] = d_data.get("name", "N/A")

        processed_matches: list[Match] = []
        for match in matches:
            m_snap = cast("DocumentSnapshot", match)
            match_data = cast("Match", m_snap.to_dict() or {})
            match_data["id"] = m_snap.id
            match_date = match_data.get("matchDate")
            if isinstance(match_date, datetime.datetime):
                match_date_formatted = match_date.strftime("%b %d")
            else:
                match_date_formatted = "N/A"

            score1 = match_data.get("player1Score", 0)
            score2 = match_data.get("player2Score", 0)

            point_diff = abs(score1 - score2)
            close_call = point_diff <= CLOSE_CALL_THRESHOLD

            match_data["date"] = match_date_formatted
            match_data["point_differential"] = point_diff
            match_data["close_call"] = close_call

            if match_data.get("matchType") == "doubles":
                team1_refs = match_data.get("team1", [])
                team2_refs = match_data.get("team2", [])
                team1_names = " & ".join(
                    [
                        players.get(str(getattr(ref, "id", "")), "N/A")
                        for ref in team1_refs
                    ]
                )
                team2_names = " & ".join(
                    [
                        players.get(str(getattr(ref, "id", "")), "N/A")
                        for ref in team2_refs
                    ]
                )

                if score1 > score2:
                    match_data["winner_name"] = team1_names
                    match_data["loser_name"] = team2_names
                    match_data["winner_score"] = score1
                    match_data["loser_score"] = score2
                else:
                    match_data["winner_name"] = team2_names
                    match_data["loser_name"] = team1_names
                    match_data["winner_score"] = score2
                    match_data["loser_score"] = score1
            else:  # singles
                p1_ref = match_data.get("player1Ref")
                p2_ref = match_data.get("player2Ref")

                p1_name = (
                    players.get(str(getattr(p1_ref, "id", "")), "N/A")
                    if p1_ref
                    else "N/A"
                )
                p2_name = (
                    players.get(str(getattr(p2_ref, "id", "")), "N/A")
                    if p2_ref
                    else "N/A"
                )

                if score1 > score2:
                    match_data["winner_name"] = p1_name
                    match_data["loser_name"] = p2_name
                    match_data["winner_score"] = score1
                    match_data["loser_score"] = score2
                else:
                    match_data["winner_name"] = p2_name
                    match_data["loser_name"] = p1_name
                    match_data["winner_score"] = score2
                    match_data["loser_score"] = score1

            processed_matches.append(match_data)

        return processed_matches
