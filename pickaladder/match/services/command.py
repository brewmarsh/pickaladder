from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from pickaladder.match.models import MatchResult, MatchSubmission
from pickaladder.teams.services import TeamService
from pickaladder.user.services.core import get_avatar_url, smart_display_name

from .calculator import MatchStatsCalculator
from .match_stats_updater import MatchStatsUpdater
from .match_validation import MatchValidationService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.user.models import UserSession


class MatchCommandService:
    """Service class for match-related write operations."""

    @staticmethod
    def record_match(
        db: Client, data: MatchSubmission | dict[str, Any], current_user: UserSession
    ) -> MatchResult:
        """Process and record a match submission."""
        user_id = current_user["uid"]
        sub = data if isinstance(data, MatchSubmission) else MatchSubmission(**data)
        MatchValidationService.validate_submission(db, sub, user_id)

        match_date = MatchCommandService._parse_match_date(sub.match_date)
        match_doc_data = MatchCommandService._prepare_match_doc_base(
            sub, user_id, match_date
        )

        side1_ref, side2_ref = MatchCommandService._resolve_match_participants(
            db, sub, match_doc_data
        )

        new_match_ref = cast("DocumentReference", db.collection("matches").document())
        batch = db.batch()
        MatchCommandService._record_match_batch(
            db,
            batch,
            new_match_ref,
            side1_ref,
            side2_ref,
            cast("DocumentReference", db.collection("users").document(user_id)),
            match_doc_data,
            sub.match_type,
        )
        batch.commit()

        return MatchCommandService._build_match_result(new_match_ref.id, match_doc_data)

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
        from firebase_admin import firestore

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
            p1_ref = cast(
                "DocumentReference", db.collection("users").document(sub.player_1_id)
            )
            p2_ref = cast(
                "DocumentReference", db.collection("users").document(sub.player_2_id)
            )
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
        from firebase_admin import firestore

        snaps_list = db.get_all([p1_ref, p2_ref])
        snaps = {s.id: s for s in snaps_list if s.exists}
        p1_snap = cast("DocumentSnapshot", snaps.get(p1_ref.id))
        p2_snap = cast("DocumentSnapshot", snaps.get(p2_ref.id))
        p1_data = p1_snap.to_dict() if p1_snap else {}
        p2_data = p2_snap.to_dict() if p2_snap else {}

        if match_type == "singles":
            MatchCommandService._denormalize_singles_players(
                match_data, p1_ref, p1_data or {}, p2_ref, p2_data or {}
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

        if match_type == "doubles":
            MatchStatsUpdater.update_user_stats_batch(
                batch,
                match_data.get("team1", []),
                match_data.get("team2", []),
                outcome["winner"],
            )

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
        from firebase_admin import firestore

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
        match_id: str, s1_raw: Any, s2_raw: Any, editor_uid: str
    ) -> None:
        """Update a match score with permission checks and stats rollback."""
        from firebase_admin import firestore

        db = firestore.client()
        try:
            s1, s2 = int(s1_raw or 0), int(s2_raw or 0)
        except (ValueError, TypeError):
            raise ValueError("Scores must be valid integers.")

        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists or not (data := match_doc.to_dict()):
            raise ValueError("Match not found.")

        MatchCommandService._check_match_edit_permissions(data, editor_uid, db)
        MatchCommandService._perform_stats_update(data, s1, s2)
        match_ref.update(MatchCommandService._get_match_updates(data, s1, s2))

    @staticmethod
    def _check_match_edit_permissions(
        data: dict[str, Any], uid: str, db: Client
    ) -> None:
        """Check if the user has permission to edit the match."""
        u_doc = cast("DocumentSnapshot", db.collection("users").document(uid).get())
        is_admin = u_doc.exists and (u_doc.to_dict() or {}).get("isAdmin", False)
        if data.get("tournamentId") and not is_admin:
            raise PermissionError("Only Admins can edit tournament matches.")
        if not is_admin and data.get("createdBy") != uid:
            raise PermissionError("You do not have permission to edit this match.")

    @staticmethod
    def _perform_stats_update(data: dict[str, Any], s1: int, s2: int) -> None:
        """Orchestrate the rollback and application of stats."""
        o1, o2 = data.get("player1Score", 0), data.get("player2Score", 0)
        if o1 != o2:
            MatchStatsUpdater.apply_stats_delta(data, o1 > o2, -1)
        if s1 != s2:
            MatchStatsUpdater.apply_stats_delta(data, s1 > s2, 1)

    @staticmethod
    def _get_match_updates(data: dict[str, Any], s1: int, s2: int) -> dict[str, Any]:
        """Calculate the updates for the match document."""
        win_slot = "team1" if s1 > s2 else "team2"
        upd = {
            "player1Score": s1,
            "player2Score": s2,
            "winner": win_slot,
            "status": "COMPLETED",
        }
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
