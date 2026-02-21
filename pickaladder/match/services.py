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
    """Utility class for match statistics calculations."""

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

        # Simple Elo Calculation (K=32)
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
            # Fallback for mockfirestore
            matches_query = db.collection("matches").limit(limit)
            matches = list(matches_query.stream())

        player_refs = MatchQueryService._get_player_refs_from_matches(matches)
        players = MatchQueryService._fetch_player_names(db, player_refs)
        return MatchQueryService._format_match_documents(matches, players)

    @staticmethod
    def _get_player_refs_from_matches(
        matches: list[DocumentSnapshot],
    ) -> set[DocumentReference]:
        """Extract all unique player references from a list of matches."""
        player_refs: set[DocumentReference] = set()
        for match in matches:
            m_data = match.to_dict()
            if not m_data:
                continue
            if m_data.get("matchType") == "doubles":
                player_refs.update(m_data.get("team1", []))
                player_refs.update(m_data.get("team2", []))
            elif "player_1_data" not in m_data or "player_2_data" not in m_data:
                if p1_ref := m_data.get("player1Ref"):
                    player_refs.add(p1_ref)
                if p2_ref := m_data.get("player2Ref"):
                    player_refs.add(p2_ref)
        return player_refs

    @staticmethod
    def _fetch_player_names(
        db: Client, player_refs: set[DocumentReference]
    ) -> dict[str, str]:
        """Fetch names for a set of player references."""
        players: dict[str, str] = {}
        if player_refs:
            player_docs = db.get_all(list(player_refs))
            for doc in player_docs:
                if doc.exists:
                    d_data = doc.to_dict() or {}
                    players[doc.id] = d_data.get("name", "N/A")
        return players

    @staticmethod
    def _format_match_documents(
        matches: list[DocumentSnapshot], players: dict[str, str]
    ) -> list[Match]:
        """Process and format match documents for display."""
        processed_matches: list[Match] = []
        for match in matches:
            match_data = cast("Match", match.to_dict() or {})
            match_data["id"] = match.id
            MatchQueryService._apply_common_match_formatting(match_data)

            if match_data.get("matchType") == "doubles":
                MatchQueryService._format_doubles_match_names(match_data, players)
            else:
                MatchQueryService._format_singles_match_names(match_data, players)

            processed_matches.append(match_data)
        return processed_matches

    @staticmethod
    def _apply_common_match_formatting(match_data: Match) -> None:
        """Apply formatting common to all match types."""
        match_date = match_data.get("matchDate")
        if isinstance(match_date, datetime.datetime):
            match_data["date"] = match_date.strftime("%b %d")
        else:
            match_data["date"] = "N/A"

        score1 = match_data.get("player1Score", 0)
        score2 = match_data.get("player2Score", 0)
        point_diff = abs(score1 - score2)

        match_data["point_differential"] = point_diff
        match_data["close_call"] = point_diff <= CLOSE_CALL_THRESHOLD

    @staticmethod
    def _format_doubles_match_names(match_data: Match, players: dict[str, str]) -> None:
        """Format names and scores for doubles matches."""
        team1_refs = match_data.get("team1", [])
        team2_refs = match_data.get("team2", [])

        t1_names = " & ".join(
            [players.get(getattr(ref, "id", ""), "N/A") for ref in team1_refs]
        )
        t2_names = " & ".join(
            [players.get(getattr(ref, "id", ""), "N/A") for ref in team2_refs]
        )

        s1, s2 = match_data.get("player1Score", 0), match_data.get("player2Score", 0)
        if s1 > s2:
            match_data.update(
                {
                    "winner_name": t1_names,
                    "loser_name": t2_names,
                    "winner_score": s1,
                    "loser_score": s2,
                }
            )
        else:
            match_data.update(
                {
                    "winner_name": t2_names,
                    "loser_name": t1_names,
                    "winner_score": s2,
                    "loser_score": s1,
                }
            )

    @staticmethod
    def _format_singles_match_names(match_data: Match, players: dict[str, str]) -> None:
        """Format names and scores for singles matches."""
        if match_data.get("player_1_data") and match_data.get("player_2_data"):
            p1_name = match_data["player_1_data"].get("display_name", "N/A")
            p2_name = match_data["player_2_data"].get("display_name", "N/A")
        else:
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")
            p1_name = players.get(getattr(p1_ref, "id", ""), "N/A") if p1_ref else "N/A"
            p2_name = players.get(getattr(p2_ref, "id", ""), "N/A") if p2_ref else "N/A"

        s1, s2 = match_data.get("player1Score", 0), match_data.get("player2Score", 0)
        if s1 > s2:
            match_data.update(
                {
                    "winner_name": p1_name,
                    "loser_name": p2_name,
                    "winner_score": s1,
                    "loser_score": s2,
                }
            )
        else:
            match_data.update(
                {
                    "winner_name": p2_name,
                    "loser_name": p1_name,
                    "winner_score": s2,
                    "loser_score": s1,
                }
            )

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
        doc = db.collection("tournaments").document(tournament_id).get()
        return (doc.to_dict() or {}).get("participant_ids", []) if doc.exists else []

    @staticmethod
    def _get_group_candidates(db: Client, group_id: str) -> set[str]:
        """Fetch group members and invited users for a group."""
        candidates = set()
        group_doc = db.collection("groups").document(group_id).get()
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
            doc.to_dict().get("email") for doc in invites if doc.to_dict().get("email")
        ]
        if emails:
            for i in range(0, len(emails), 30):
                users = (
                    db.collection("users")
                    .where(filter=firestore.FieldFilter("email", "in", emails[i : i + 30]))
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates

    @staticmethod
    def _get_default_candidates(db: Client, user_id: str) -> set[str]:
        """Fetch friends and personal invitees for a user."""
        candidates = set()
        friends = (
            db.collection("users").document(user_id).collection("friends").stream()
        )
        candidates.update(
            f.id
            for f in friends
            if f.to_dict().get("status") in ["accepted", "pending"]
        )

        invites = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
            .stream()
        )
        emails = list(
            {doc.to_dict().get("email") for doc in invites if doc.to_dict().get("email")}
        )
        if emails:
            for i in range(0, len(emails), 10):
                users = (
                    db.collection("users")
                    .where(filter=firestore.FieldFilter("email", "in", emails[i : i + 10]))
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates

    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference."""
        wins, losses = 0, 0
        queries = [
            db.collection("matches").where(
                filter=firestore.FieldFilter("player1Ref", "==", player_ref)
            ),
            db.collection("matches").where(
                filter=firestore.FieldFilter("player2Ref", "==", player_ref)
            ),
            db.collection("matches").where(
                filter=firestore.FieldFilter("team1", "array_contains", player_ref)
            ),
            db.collection("matches").where(
                filter=firestore.FieldFilter("team2", "array_contains", player_ref)
            ),
        ]

        for idx, query in enumerate(queries):
            for match in query.stream():
                data = match.to_dict()
                if not data:
                    continue
                is_doubles = data.get("matchType") == "doubles"
                if (idx < 2 and is_doubles) or (idx >= 2 and not is_doubles):
                    continue

                s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
                if (idx % 2 == 0 and s1 > s2) or (idx % 2 == 1 and s2 > s1):
                    wins += 1
                else:
                    losses += 1
        return {"wins": wins, "losses": losses}

    @staticmethod
    def get_match_summary_context(db: Client, match_id: str) -> dict[str, Any]:
        """Fetch all data needed for the match summary view."""
        match_data = MatchQueryService.get_match_by_id(db, match_id)
        if not match_data:
            return {}

        match_type = match_data.get("matchType", "singles")
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
                    if doc.exists:
                        d = doc.to_dict() or {}
                        d["id"] = doc.id
                        team_data.append(d)
            return team_data

        return {
            "team1": fetch_team(match_data.get("team1", [])),
            "team2": fetch_team(match_data.get("team2", [])),
        }

    @staticmethod
    def _get_singles_summary_context(db: Client, match_data: Match) -> dict[str, Any]:
        """Fetch singles-specific context for match summary."""
        res = {}
        for key, ref_key in [("player1", "player1Ref"), ("player2", "player2Ref")]:
            ref = match_data.get(ref_key)
            data, record = {}, {"wins": 0, "losses": 0}
            if ref:
                snap = ref.get()
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
        from pickaladder.user.services.match_stats import format_matches_for_dashboard

        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("participants", "array_contains", uid))
            .order_by("matchDate", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        if start_after:
            last_doc = db.collection("matches").document(start_after).get()
            if last_doc.exists:
                query = query.start_after(last_doc)

        docs = list(query.stream())
        return (
            (format_matches_for_dashboard(db, docs, uid), docs[-1].id) if docs else ([], None)
        )

    @staticmethod
    def get_player_names(db: Client, uids: Iterable[str]) -> dict[str, str]:
        """Fetch a mapping of UIDs to names."""
        names: dict[str, str] = {}
        if uids:
            for doc in db.get_all([db.collection("users").document(uid) for uid in uids]):
                if doc.exists:
                    names[doc.id] = (doc.to_dict() or {}).get("name", doc.id)
        return names

    @staticmethod
    def get_tournament_name(db: Client, tournament_id: str) -> str | None:
        """Fetch tournament name."""
        doc = db.collection("tournaments").document(tournament_id).get()
        return (doc.to_dict() or {}).get("name") if doc.exists else None

    @staticmethod
    def get_user_last_match_type(db: Client, user_id: str) -> str:
        """Fetch the last match type recorded by the user."""
        doc = db.collection("users").document(user_id).get()
        return (
            (doc.to_dict() or {}).get("lastMatchRecordedType", "singles")
            if doc.exists
            else "singles"
        )

    @staticmethod
    def get_team_names(db: Client, team1_id: str, team2_id: str) -> tuple[str, str]:
        """Fetch names for two teams."""
        t1 = db.collection("teams").document(team1_id).get()
        t2 = db.collection("teams").document(team2_id).get()
        return (
            (t1.to_dict() or {}).get("name", "Team 1") if t1.exists else "Team 1",
            (t2.to_dict() or {}).get("name", "Team 2") if t2.exists else "Team 2",
        )


class MatchCommandService:
    """Service class for match-related write operations."""

    @staticmethod
    def record_match(
        db: Client, submission: MatchSubmission, current_user: UserSession
    ) -> MatchResult:
        """Process and record a match submission."""
        user_id = current_user["uid"]
        MatchCommandService._validate_submission(db, submission, user_id)

        match_date = MatchCommandService._parse_match_date(submission.match_date)
        match_doc_data = MatchCommandService._prepare_match_doc_base(
            submission, user_id, match_date
        )

        side1_ref, side2_ref = MatchCommandService._resolve_match_participants(
            db, submission, match_doc_data
        )

        new_match_ref = db.collection("matches").document()
        batch = db.batch()
        MatchCommandService._record_match_batch(
            db,
            batch,
            new_match_ref,
            side1_ref,
            side2_ref,
            db.collection("users").document(user_id),
            match_doc_data,
            submission.match_type,
        )
        batch.commit()

        return MatchCommandService._build_match_result(new_match_ref.id, match_doc_data)

    @staticmethod
    def _validate_submission(db: Client, sub: MatchSubmission, user_id: str) -> None:
        """Validate that all players are valid candidates."""
        cands = MatchQueryService.get_candidate_player_ids(
            db, user_id, sub.group_id, sub.tournament_id
        )
        p1_cands = MatchQueryService.get_candidate_player_ids(
            db, user_id, sub.group_id, sub.tournament_id, True
        )

        if sub.player_1_id not in p1_cands:
            raise ValueError("Invalid Team 1 Player 1 selected.")
        if sub.player_2_id not in cands:
            raise ValueError("Invalid Opponent 1 selected.")
        if sub.match_type == "doubles":
            if sub.partner_id not in cands:
                raise ValueError("Invalid Partner selected.")
            if sub.opponent_2_id not in cands:
                raise ValueError("Invalid Opponent 2 selected.")

    @staticmethod
    def _parse_match_date(date_input: Any) -> datetime.datetime:
        """Parse match date input into a timezone-aware datetime."""
        if isinstance(date_input, str) and date_input:
            return datetime.datetime.strptime(date_input, "%Y-%m-%d").replace(
                tzinfo=datetime.timezone.utc
            )
        if isinstance(date_input, datetime.date) and not isinstance(
            date_input, datetime.datetime
        ):
            return datetime.datetime.combine(date_input, datetime.time.min).replace(
                tzinfo=datetime.timezone.utc
            )
        if isinstance(date_input, datetime.datetime):
            return date_input.replace(tzinfo=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc)

    @staticmethod
    def _prepare_match_doc_base(
        sub: MatchSubmission, user_id: str, date: datetime.datetime
    ) -> dict[str, Any]:
        """Prepare the base data dictionary for the match document."""
        data = {
            "player1Score": sub.score_p1,
            "player2Score": sub.score_p2,
            "matchDate": date,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": sub.match_type,
            "createdBy": user_id,
        }
        if sub.group_id:
            data["groupId"] = sub.group_id
        if sub.tournament_id:
            data["tournamentId"] = sub.tournament_id
        return data

    @staticmethod
    def _resolve_match_participants(
        db: Client, sub: MatchSubmission, data: dict[str, Any]
    ) -> tuple[DocumentReference, DocumentReference]:
        """Resolve player/team references based on match type."""
        if sub.match_type == "singles":
            p1_ref = db.collection("users").document(sub.player_1_id)
            p2_ref = db.collection("users").document(sub.player_2_id)
            data.update(
                {
                    "player1Ref": p1_ref,
                    "player2Ref": p2_ref,
                    "participants": [sub.player_1_id, sub.player_2_id],
                }
            )
            return p1_ref, p2_ref

        res = MatchCommandService._resolve_teams(
            db,
            sub.player_1_id,
            cast(str, sub.partner_id),
            cast(str, sub.player_2_id),
            cast(str, sub.opponent_2_id),
        )
        data.update(res)
        data["participants"] = [
            sub.player_1_id,
            sub.partner_id,
            sub.player_2_id,
            sub.opponent_2_id,
        ]
        return cast("DocumentReference", res["team1Ref"]), cast(
            "DocumentReference", res["team2Ref"]
        )

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
        snaps = {s.id: s for s in db.get_all([p1_ref, p2_ref]) if s.exists}
        p1_data = snaps.get(p1_ref.id).to_dict() if snaps.get(p1_ref.id) else {}
        p2_data = snaps.get(p2_ref.id).to_dict() if snaps.get(p2_ref.id) else {}

        if match_type == "singles":
            MatchCommandService._denormalize_singles_players(
                match_data, p1_ref, p1_data, p2_ref, p2_data
            )

        outcome = MatchStatsCalculator.calculate_match_outcome(
            match_data["player1Score"], match_data["player2Score"], p1_ref.id, p2_ref.id
        )
        match_data.update(outcome)

        p1_upd, p2_upd = MatchStatsCalculator.calculate_elo_updates(
            outcome["winner"], p1_data, p2_data
        )
        if match_type == "singles" and MatchStatsCalculator.check_upset(
            outcome["winner"], p1_data, p2_data
        ):
            match_data["is_upset"] = True

        batch.set(match_ref, match_data)
        batch.update(p1_ref, p1_upd)
        batch.update(p2_ref, p2_upd)
        batch.update(user_ref, {"lastMatchRecordedType": match_type})

        if gid := match_data.get("groupId"):
            batch.update(
                db.collection("groups").document(gid),
                {"updatedAt": firestore.SERVER_TIMESTAMP},
            )

    @staticmethod
    def _denormalize_singles_players(
        data: dict[str, Any],
        p1_ref: DocumentReference,
        p1_data: dict[str, Any],
        p2_ref: DocumentReference,
        p2_data: dict[str, Any],
    ) -> None:
        """Denormalize player data into the match document for singles."""
        for ref, d, key in [
            (p1_ref, p1_data, "player_1_data"),
            (p2_ref, p2_data, "player_2_data"),
        ]:
            data[key] = {
                "uid": ref.id,
                "display_name": smart_display_name(d),
                "avatar_url": get_avatar_url(d),
                "dupr_at_match_time": float(
                    d.get("duprRating") or d.get("dupr_rating") or 0.0
                ),
            }

    @staticmethod
    def _build_match_result(match_id: str, data: dict[str, Any]) -> MatchResult:
        """Construct a MatchResult from the match data."""
        return MatchResult(
            id=match_id,
            matchType=data.get("matchType", ""),
            player1Score=data.get("player1Score", 0),
            player2Score=data.get("player2Score", 0),
            matchDate=data.get("matchDate"),
            createdAt=data.get("createdAt", firestore.SERVER_TIMESTAMP),
            createdBy=data.get("createdBy", ""),
            winner=data.get("winner", ""),
            winnerId=data.get("winnerId", ""),
            loserId=data.get("loserId", ""),
            groupId=data.get("groupId"),
            tournamentId=data.get("tournamentId"),
            player1Ref=data.get("player1Ref"),
            player2Ref=data.get("player2Ref"),
            team1=data.get("team1"),
            team2=data.get("team2"),
            team1Id=data.get("team1Id"),
            team2Id=data.get("team2Id"),
            team1Ref=data.get("team1Ref"),
            team2Ref=data.get("team2Ref"),
            is_upset=data.get("is_upset", False),
        )

    @staticmethod
    def _resolve_teams(
        db: Client, t1p1: str, t1p2: str, t2p1: str, t2p2: str
    ) -> dict[str, Any]:
        """Resolve and create/fetch teams for doubles matches."""
        id1 = TeamService.get_or_create_team(db, t1p1, t1p2)
        id2 = TeamService.get_or_create_team(db, t2p1, t2p2)
        return {
            "team1": [
                db.collection("users").document(t1p1),
                db.collection("users").document(t1p2),
            ],
            "team2": [
                db.collection("users").document(t2p1),
                db.collection("users").document(t2p2),
            ],
            "team1Id": id1,
            "team2Id": id2,
            "team1Ref": db.collection("teams").document(id1),
            "team2Ref": db.collection("teams").document(id2),
        }

    @staticmethod
    def update_match_score(
        db: Client, match_id: str, s1: int, s2: int, editor_uid: str
    ) -> None:
        """Update a match score with permission checks and stats rollback."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = match_ref.get()
        if not match_doc.exists or not (data := match_doc.to_dict()):
            raise ValueError("Match not found.")

        MatchCommandService._check_match_edit_permissions(data, editor_uid, db)
        MatchCommandService._update_doubles_stats(data, s1, s2)
        match_ref.update(MatchCommandService._get_match_updates(data, s1, s2))

    @staticmethod
    def _check_match_edit_permissions(data: dict[str, Any], uid: str, db: Client) -> None:
        """Check if the user has permission to edit the match."""
        is_admin = (
            d := db.collection("users").document(uid).get()
        ).exists and (d.to_dict() or {}).get("isAdmin", False)
        if data.get("tournamentId") and not is_admin:
            raise PermissionError("Only Admins can edit tournament matches.")
        if not is_admin and data.get("createdBy") != uid:
            raise PermissionError("You do not have permission to edit this match.")

    @staticmethod
    def _update_doubles_stats(data: dict[str, Any], s1: int, s2: int) -> None:
        """Rollback old stats and apply new stats for doubles matches."""
        if (
            data.get("matchType") != "doubles"
            or not (r1 := data.get("team1Ref"))
            or not (r2 := data.get("team2Ref"))
        ):
            return
        o1, o2 = data.get("player1Score", 0), data.get("player2Score", 0)

        if o1 > o2:
            r1.update({"stats.wins": firestore.Increment(-1)})
            r2.update({"stats.losses": firestore.Increment(-1)})
        elif o2 > o1:
            r2.update({"stats.wins": firestore.Increment(-1)})
            r1.update({"stats.losses": firestore.Increment(-1)})

        if s1 > s2:
            r1.update({"stats.wins": firestore.Increment(1)})
            r2.update({"stats.losses": firestore.Increment(1)})
        elif s2 > s1:
            r2.update({"stats.wins": firestore.Increment(1)})
            r1.update({"stats.losses": firestore.Increment(1)})

    @staticmethod
    def _get_match_updates(data: dict[str, Any], s1: int, s2: int) -> dict[str, Any]:
        """Calculate the updates for the match document."""
        win_slot = "team1" if s1 > s2 else "team2"
        upd = {"player1Score": s1, "player2Score": s2, "winner": win_slot}
        if data.get("matchType") == "doubles":
            upd["winnerId"] = data.get("team1Id" if s1 > s2 else "team2Id")
            upd["loserId"] = data.get("team2Id" if s1 > s2 else "team1Id")
        else:
            p1, p2 = data.get("player1Ref"), data.get("player2Ref")
            if p1 and p2:
                upd["winnerId"], upd["loserId"] = (
                    (p1.id, p2.id) if s1 > s2 else (p2.id, p1.id)
                )
        return upd


