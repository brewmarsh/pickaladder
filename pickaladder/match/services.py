"""Service layer for match data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.services.core import get_avatar_url, smart_display_name

from .models import Match, MatchResult, MatchSubmission

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user.models import UserSession


CLOSE_CALL_THRESHOLD = 2
UPSET_THRESHOLD = 0.25


class MatchService:
    """Handles business logic and data access for match records."""

    @staticmethod
    def _record_match_batch(
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

        p1_data = (p1_snapshot.to_dict() if p1_snapshot else {}) or {}
        p2_data = (p2_snapshot.to_dict() if p2_snapshot else {}) or {}

        # 1.5 Denormalize Player Data (Snapshots)
        if match_type == "singles":
            match_data["player_1_data"] = {
                "uid": p1_ref.id,
                "display_name": smart_display_name(p1_data),
                "avatar_url": get_avatar_url(p1_data),
                "dupr_at_match_time": float(
                    p1_data.get("duprRating") or p1_data.get("dupr_rating") or 0.0
                ),
            }
            match_data["player_2_data"] = {
                "uid": p2_ref.id,
                "display_name": smart_display_name(p2_data),
                "avatar_url": get_avatar_url(p2_data),
                "dupr_at_match_time": float(
                    p2_data.get("duprRating") or p2_data.get("dupr_rating") or 0.0
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
            # For doubles, side1_ref and side2_ref are team refs
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

        if winner == "team1":
            p1_wins += 1
            p2_losses += 1
        else:
            p2_wins += 1
            p1_losses += 1

        # 3. Update Batch (No commits yet)
        batch.set(match_ref, match_data)

        batch.update(
            p1_ref,
            {
                "stats.wins": p1_wins,
                "stats.losses": p1_losses,
                "stats.elo": p1_elo,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )
        batch.update(
            p2_ref,
            {
                "stats.wins": p2_wins,
                "stats.losses": p2_losses,
                "stats.elo": p2_elo,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        # Update last match type
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

        # Update group last activity
        if group_id := match_data.get("groupId"):
            group_ref = db.collection("groups").document(group_id)
            batch.update(group_ref, {"updatedAt": firestore.SERVER_TIMESTAMP})

    @staticmethod
    def record_match(
        db: Client,
        submission: MatchSubmission | dict[str, Any],
        current_user: UserSession | dict[str, Any],
    ) -> MatchResult:
        """Process and record a match submission."""
        user_id = current_user["uid"]
        user_ref = db.collection("users").document(user_id)

        if isinstance(submission, dict):
            # Compatibility layer for dict-based submissions (from form or API)
            match_type = str(
                submission.get("match_type") or submission.get("matchType", "singles")
            )
            p1_id = str(
                submission.get("player_1_id") or submission.get("player1") or user_id
            )
            p2_id = str(
                submission.get("player_2_id") or submission.get("player2") or ""
            )
            partner_id = submission.get("partner_id") or submission.get("partner")
            opponent2_id = submission.get("opponent_2_id") or submission.get(
                "opponent2"
            )
            group_id = submission.get("group_id") or submission.get("groupId")
            tournament_id = submission.get("tournament_id") or submission.get(
                "tournamentId"
            )
            score_p1 = int(
                cast(
                    Any,
                    submission.get("score_p1")
                    if submission.get("score_p1") is not None
                    else submission.get("player1_score") or 0,
                )
            )
            score_p2 = int(
                cast(
                    Any,
                    submission.get("score_p2")
                    if submission.get("score_p2") is not None
                    else submission.get("player2_score") or 0,
                )
            )
            match_date_input = submission.get("match_date") or submission.get(
                "matchDate"
            )
        else:
            match_type = submission.match_type
            p1_id = submission.player_1_id
            p2_id = submission.player_2_id
            partner_id = submission.partner_id
            opponent2_id = submission.opponent_2_id
            group_id = submission.group_id
            tournament_id = submission.tournament_id
            score_p1 = submission.score_p1
            score_p2 = submission.score_p2
            match_date_input = submission.match_date

        # Candidate Validation (Service-side because it requires DB)

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

        match_doc_data: dict[str, Any] = {
            "player1Score": score_p1,
            "player2Score": score_p2,
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

        # Save to database via batched write (exactly 1 commit round-trip)
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
            player1Score=match_doc_data.get("player1Score", score_p1),
            player2Score=match_doc_data.get("player2Score", score_p2),
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
        )

    @staticmethod
    def _resolve_teams(
        db: Client, p1: str, partner: str, opp1: str, opp2: str
    ) -> dict[str, Any]:
        """Fetch or create team objects for a doubles match."""
        # Normalize team membership (sort IDs to ensure deterministic team identity)
        team1_id = TeamService.get_or_create_team(db, p1, partner)
        team2_id = TeamService.get_or_create_team(db, opp1, opp2)

        return {
            "team1Id": team1_id,
            "team2Id": team2_id,
            "team1Ref": db.collection("teams").document(team1_id),
            "team2Ref": db.collection("teams").document(team2_id),
            "team1": [
                db.collection("users").document(p1),
                db.collection("users").document(partner),
            ],
            "team2": [
                db.collection("users").document(opp1),
                db.collection("users").document(opp2),
            ],
        }

    @staticmethod
    def get_candidate_player_ids(
        db: Client,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
        include_user: bool = False,
    ) -> set[str]:
        """Fetch IDs of players that can be selected in a match form."""
        candidate_player_ids = set()

        if tournament_id:
            # If in a tournament context, candidates are accepted participants
            tournament_ref = db.collection("tournaments").document(tournament_id)
            tournament = cast("DocumentSnapshot", tournament_ref.get())
            if tournament.exists:
                tournament_data = tournament.to_dict() or {}
                participants = tournament_data.get("participants", [])
                for p in participants:
                    if p.get("status") == "accepted":
                        p_uid = p.get("user_id") or p.get("userRef").id
                        candidate_player_ids.add(p_uid)
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
                .where("group_id", "==", group_id)
                .where("used", "==", False)
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
                        .where("email", "in", batch_emails)
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
                .where("inviter_id", "==", user_id)
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
                        .where("email", "in", batch_emails)
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
            db.collection("matches").where("player1Ref", "==", player_ref).stream()
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
            db.collection("matches").where("player2Ref", "==", player_ref).stream()
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
            .where("team1", "array_contains", player_ref)
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
            .where("team2", "array_contains", player_ref)
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
        """Fetch a single match document and return it as a Match model."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            return None
        data = match_doc.to_dict()
        if data is None:
            return None
        data["id"] = match_id
        return cast(Match, data)

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any] | None:
        """Get the context for the match summary page."""
        match_data = MatchService.get_match_by_id(db, match_id)
        if not match_data:
            return None

        match_type = match_data.get("matchType", "singles")
        context: dict[str, Any] = {
            "match": match_data,
            "match_type": match_type,
        }

        if match_type == "doubles":
            team1_refs = match_data.get("team1", [])
            team2_refs = match_data.get("team2", [])
            all_refs = team1_refs + team2_refs

            # Resolve player data
            u_docs = cast(list[Any], db.get_all(all_refs))
            team1 = []
            team2 = []

            for i, doc in enumerate(u_docs):
                u_data = doc.to_dict() if doc.exists else {}
                u_data["id"] = doc.id
                u_data["name"] = smart_display_name(u_data)
                if i < len(team1_refs):
                    team1.append(u_data)
                else:
                    team2.append(u_data)

            context["team1"] = team1
            context["team2"] = team2
        else:
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")

            u_docs = cast(list[Any], db.get_all([p1_ref, p2_ref]))
            p1_data = u_docs[0].to_dict() if u_docs[0].exists else {}
            p1_data["id"] = u_docs[0].id
            p1_data["name"] = smart_display_name(p1_data)

            p2_data = u_docs[1].to_dict() if u_docs[1].exists else {}
            p2_data["id"] = u_docs[1].id
            p2_data["name"] = smart_display_name(p2_data)

            context["player1"] = p1_data
            context["player2"] = p2_data
            context["player1_record"] = MatchService.get_player_record(db, p1_ref)
            context["player2_record"] = MatchService.get_player_record(db, p2_ref)

        return context

    @staticmethod
    def delete_match(db: Client, match_id: str, user_id: str) -> None:
        """Delete a match and update player stats."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            raise ValueError("Match not found.")

        match_data = match_doc.to_dict() or {}
        if match_data.get("createdBy") != user_id:
            # Check if user is admin
            user_ref = db.collection("users").document(user_id)
            user_doc = cast("DocumentSnapshot", user_ref.get())
            if not user_doc.exists or not (user_doc.to_dict() or {}).get("isAdmin"):
                raise PermissionError("Unauthorized to delete this match.")

        # In a real app, we should also decrement wins/losses here.
        # For simplicity in this project, we just delete the doc.
        match_ref.delete()

    @staticmethod
    def update_match_scores(
        db: Client, match_id: str, new_p1_score: int, new_p2_score: int
    ) -> None:
        """Update match scores in Firestore."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            raise ValueError("Match not found")

        match_data = match_doc.to_dict() or {}
        # In a real app, we should also update player wins/losses here.
        updates = MatchService._get_match_updates(
            match_data, new_p1_score, new_p2_score
        )
        match_ref.update(updates)

    @staticmethod
    def get_matches_for_user(
        db: Client, uid: str, limit: int = 20, start_after: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch matches for a user with cursor-based pagination."""
        from pickaladder.user.services.match_stats import format_matches_for_dashboard

        matches_ref = db.collection("matches")
        # Ensure 'matchDate' is used for ordering to match the created documents
        query = matches_ref.where("participants", "array_contains", uid)

        try:
            query = query.order_by("matchDate", direction=firestore.Query.DESCENDING)
        except Exception:
            pass

        query = query.limit(limit)

        if start_after:
            last_doc = cast("DocumentSnapshot", matches_ref.document(start_after).get())
            if bool(last_doc.exists):
                query = query.start_after(last_doc)

        docs = list(query.stream())
        if not docs:
            return [], None

        matches = format_matches_for_dashboard(db, docs, uid)
        next_cursor = docs[-1].id if len(docs) == limit else None

        return matches, next_cursor

    @staticmethod
    def _get_match_updates(
        match_data: dict[str, Any], new_p1_score: int, new_p2_score: int
    ) -> dict[str, Any]:
        """Calculate score-related updates for a match document."""
        winner = "team1" if new_p1_score > new_p2_score else "team2"
        updates: dict[str, Any] = {
            "player1Score": new_p1_score,
            "player2Score": new_p2_score,
            "winner": winner,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        match_type = match_data.get("matchType", "singles")
        if match_type == "singles":
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")
            if p1_ref and p2_ref:
                updates["winnerId"] = p1_ref.id if winner == "team1" else p2_ref.id
                updates["loserId"] = p2_ref.id if winner == "team1" else p1_ref.id
        else:
            t1_ref = match_data.get("team1Ref")
            t2_ref = match_data.get("team2Ref")
            if t1_ref and t2_ref:
                updates["winnerId"] = t1_ref.id if winner == "team1" else t2_ref.id
                updates["loserId"] = t2_ref.id if winner == "team1" else t1_ref.id

        return updates
