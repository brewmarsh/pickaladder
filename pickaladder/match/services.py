"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES
from pickaladder.teams.services import TeamService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.batch import WriteBatch

    from pickaladder.user import User
    from pickaladder.user.models import UserSession

    from .models import Match


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

        p1_data = p1_snapshot.to_dict() if p1_snapshot else {}
        p2_data = p2_snapshot.to_dict() if p2_snapshot else {}

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
            # For doubles, side1_ref and side2_ref are team refs
            match_data["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
            match_data["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id

        def get_stat(data: dict[str, Any], key: str, default: Any) -> Any:
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

        # Update the Group "leaderboard document" (the group doc itself)
        if group_id := match_data.get("groupId"):
            group_ref = db.collection("groups").document(group_id)
            batch.update(group_ref, {"updatedAt": firestore.SERVER_TIMESTAMP})

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
            "createdBy": user_id,
        }

        # Add IDs if present
        if group_id:
            match_doc_data["groupId"] = group_id
        if tournament_id:
            match_doc_data["tournamentId"] = tournament_id

        if match_type == "singles":
            p1_ref = db.collection("users").document(p1_id)
            p2_ref = db.collection("users").document(p2_id)
            match_doc_data["player1Ref"] = p1_ref
            match_doc_data["player2Ref"] = p2_ref
            side1_ref = p1_ref
            side2_ref = p2_ref
        elif match_type == "doubles":
            res = MatchService._resolve_teams(
                db, p1_id, cast(str, partner_id), p2_id, cast(str, opponent2_id)
            )
            match_doc_data.update(res)
            side1_ref = cast("DocumentReference", res.get("team1Ref"))
            side2_ref = cast("DocumentReference", res.get("team2Ref"))
        else:
            raise ValueError("Unsupported match type.")

        # Save to database via batched write (exactly 1 commit round-trip)
        new_match_ref = db.collection("matches").document()
        batch = db.batch()
        MatchService._record_match_batch(
            db,
            batch,
            new_match_ref,
            side1_ref,
            side2_ref,
            user_ref,
            match_doc_data,
            match_type,
        )
        batch.commit()

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
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
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

            # Only include players with at least minimum games played to ensure
            # a representative leaderboard and filter inactive players.
            if games_played >= min_games:
                players.append(user_data)

        # Sort players by win percentage, then by wins
        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True
        )
        return players[:limit]

    @staticmethod
    def update_match_score(  # noqa: PLR0913
        db: Client,
        match_id: str,
        new_p1_score: int,
        new_p2_score: int,
        editor_uid: str,
    ) -> None:
        """Update a match score with permission checks and stats rollback."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            raise ValueError("Match not found.")

        match_data = match_doc.to_dict()
        if match_data is None:
            raise ValueError("Match data is empty.")

        tournament_id = match_data.get("tournamentId")
        created_by = match_data.get("createdBy")

        # Permission Check
        editor_ref = db.collection("users").document(editor_uid)
        editor_doc = cast("DocumentSnapshot", editor_ref.get())
        is_admin = False
        if editor_doc.exists:
            editor_data = editor_doc.to_dict()
            if editor_data:
                is_admin = editor_data.get("isAdmin", False)

        if tournament_id:
            if not is_admin:
                raise PermissionError("Only Admins can edit tournament matches.")
        elif not is_admin and created_by != editor_uid:
            raise PermissionError("You do not have permission to edit this match.")

        # Stats Rollback Logic (for doubles only, as singles are dynamic)
        old_p1_score = match_data.get("player1Score", 0)
        old_p2_score = match_data.get("player2Score", 0)

        if match_data.get("matchType") == "doubles":
            team1_ref = match_data.get("team1Ref")
            team2_ref = match_data.get("team2Ref")

            if team1_ref and team2_ref:
                # Rollback old stats
                if old_p1_score > old_p2_score:
                    team1_ref.update({"stats.wins": firestore.Increment(-1)})
                    team2_ref.update({"stats.losses": firestore.Increment(-1)})
                elif old_p2_score > old_p1_score:
                    team2_ref.update({"stats.wins": firestore.Increment(-1)})
                    team1_ref.update({"stats.losses": firestore.Increment(-1)})

                # Apply new stats
                if new_p1_score > new_p2_score:
                    team1_ref.update({"stats.wins": firestore.Increment(1)})
                    team2_ref.update({"stats.losses": firestore.Increment(1)})
                elif new_p2_score > new_p1_score:
                    team2_ref.update({"stats.wins": firestore.Increment(1)})
                    team1_ref.update({"stats.losses": firestore.Increment(1)})

        # Update Match Document
        new_winner_slot = "team1" if new_p1_score > new_p2_score else "team2"

        updates: dict[str, Any] = {
            "player1Score": new_p1_score,
            "player2Score": new_p2_score,
            "winner": new_winner_slot,
        }

        if match_data.get("matchType") == "doubles":
            updates["winnerId"] = (
                match_data.get("team1Id")
                if new_p1_score > new_p2_score
                else match_data.get("team2Id")
            )
            updates["loserId"] = (
                match_data.get("team2Id")
                if new_p1_score > new_p2_score
                else match_data.get("team1Id")
            )
        else:
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")
            if p1_ref and p2_ref:
                updates["winnerId"] = (
                    p1_ref.id if new_p1_score > new_p2_score else p2_ref.id
                )
                updates["loserId"] = (
                    p2_ref.id if new_p1_score > new_p2_score else p1_ref.id
                )

        match_ref.update(updates)

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
