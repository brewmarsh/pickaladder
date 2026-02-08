"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.utils import get_or_create_team

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

    from pickaladder.match.models import Match
    from pickaladder.user.models import User


CLOSE_CALL_THRESHOLD = 2


class MatchService:
    """Service class for match-related operations."""

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
        candidate_player_ids: set[str] = set()

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
    def save_match_data(
        db: Client,
        player_1_id: str,
        form_data: Any,
        group_id: str | None = None,
        tournament_id: str | None = None,
    ) -> None:
        """Construct and save a match document to Firestore."""
        user_ref = db.collection("users").document(player_1_id)

        # Handle both form objects and dictionaries
        def get_data(key: str) -> Any:
            if isinstance(form_data, dict):
                return form_data.get(key)
            return getattr(form_data, key).data

        match_type = get_data("match_type")
        match_date_input = get_data("match_date")

        if isinstance(match_date_input, str) and match_date_input:
            match_date = datetime.datetime.strptime(match_date_input, "%Y-%m-%d")
        elif isinstance(match_date_input, datetime.date):
            match_date = datetime.datetime.combine(match_date_input, datetime.time.min)
        else:
            match_date = datetime.datetime.now()

        player1_score = int(get_data("player1_score"))
        player2_score = int(get_data("player2_score"))

        match_data: dict[str, Any] = {
            "player1Score": player1_score,
            "player2Score": player2_score,
            "matchDate": match_date,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": match_type,
        }

        if group_id:
            match_data["groupId"] = group_id
        if tournament_id:
            match_data["tournamentId"] = tournament_id

        if match_type == "singles":
            player1_ref = db.collection("users").document(get_data("player1"))
            player2_ref = db.collection("users").document(get_data("player2"))
            match_data["player1Ref"] = player1_ref
            match_data["player2Ref"] = player2_ref
        elif match_type == "doubles":
            t1_p1_id = get_data("player1")
            t1_p2_id = get_data("partner")
            t2_p1_id = get_data("player2")
            t2_p2_id = get_data("opponent2")

            team1_id = get_or_create_team(t1_p1_id, t1_p2_id)
            team2_id = get_or_create_team(t2_p1_id, t2_p2_id)

            t1_p1_ref = db.collection("users").document(t1_p1_id)
            t1_p2_ref = db.collection("users").document(t1_p2_id)
            t2_p1_ref = db.collection("users").document(t2_p1_id)
            t2_p2_ref = db.collection("users").document(t2_p2_id)

            team1_ref = db.collection("teams").document(team1_id)
            team2_ref = db.collection("teams").document(team2_id)

            match_data["team1"] = [t1_p1_ref, t1_p2_ref]
            match_data["team2"] = [t2_p1_ref, t2_p2_ref]
            match_data["team1Id"] = team1_id
            match_data["team2Id"] = team2_id
            match_data["team1Ref"] = team1_ref
            match_data["team2Ref"] = team2_ref
            if player1_score > player2_score:
                team1_ref.update({"stats.wins": firestore.Increment(1)})
                team2_ref.update({"stats.losses": firestore.Increment(1)})
            elif player2_score > player1_score:
                team1_ref.update({"stats.losses": firestore.Increment(1)})
                team2_ref.update({"stats.wins": firestore.Increment(1)})

        db.collection("matches").add(match_data)
        user_ref.update({"lastMatchRecordedType": match_type})

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
        users_query = db.collection("users").limit(limit).stream()
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
            players.append(user_data)

        # Sort players by win percentage, then by wins
        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True
        )
        return players

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
