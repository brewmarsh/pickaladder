from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from pickaladder.base.repository import BaseRepository
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
    from google.cloud.firestore_v1.transaction import Transaction

    from pickaladder.user.models import UserSession


class MatchCommandService(BaseRepository):
    """Service class for match-related write operations."""

    COLLECTION_NAME = "matches"

    @classmethod
    def record_match(
        cls,
        db: Client,
        data: MatchSubmission | dict[str, Any],
        current_user: UserSession,
    ) -> MatchResult:
        """Process and record a match submission."""
        from firebase_admin import firestore

        user_id = current_user["uid"]
        sub = data if isinstance(data, MatchSubmission) else MatchSubmission(**data)
        MatchValidationService.validate_submission(db, sub, user_id)

        match_date = cls._parse_match_date(sub.match_date)
        match_doc_data = cls._prepare_match_doc_base(sub, user_id, match_date)

        side1_ref, side2_ref = cls._resolve_match_participants(db, sub, match_doc_data)

        new_match_ref = cast(
            "DocumentReference", db.collection(cls.COLLECTION_NAME).document()
        )
        transaction = db.transaction()

        @firestore.transactional
        def _execute_match_transaction(
            transaction: Transaction,
            match_ref: DocumentReference,
            side_refs: tuple[DocumentReference, DocumentReference],
            user_ref: DocumentReference,
            match_data: dict[str, Any],
            match_type: str,
        ) -> None:
            cls._record_match_atomic(
                db,
                transaction,
                match_ref,
                side_refs,
                user_ref,
                match_data,
                match_type,
            )

        _execute_match_transaction(
            transaction,
            new_match_ref,
            (side1_ref, side2_ref),
            cast("DocumentReference", db.collection("users").document(user_id)),
            match_doc_data,
            sub.match_type,
        )

        return cls._build_match_result(new_match_ref.id, match_doc_data)

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

    @classmethod
    def _resolve_match_participants(
        cls, db: Client, sub: MatchSubmission, data: dict[str, Any]
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

        res = cls._resolve_teams(
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

    @classmethod
    def _record_match_atomic(  # noqa: PLR0913
        cls,
        db: Client,
        transaction: Transaction | WriteBatch,
        match_ref: DocumentReference,
        side_refs: tuple[DocumentReference, DocumentReference],
        user_ref: DocumentReference,
        match_data: dict[str, Any],
        match_type: str,
    ) -> None:
        """Record a match and update stats atomically."""
        from firebase_admin import firestore
        from google.cloud.firestore_v1.transaction import Transaction

        p1_ref, p2_ref = side_refs

        # Perform all reads first
        read_refs = [p1_ref, p2_ref]
        side1_ids, side2_ids = cls._get_side_ids(match_data, match_type)
        all_participant_ids = list(set(side1_ids + side2_ids))
        stats_refs = []
        if isinstance(transaction, Transaction):
            for uid in all_participant_ids:
                stats_refs.append(
                    db.collection("users")
                    .document(uid)
                    .collection("stats")
                    .document("lifetime")
                )
            read_refs.extend(stats_refs)

        # get_all only accepts transaction if it's not None
        actual_transaction = (
            transaction if isinstance(transaction, Transaction) else None
        )
        snaps_list = db.get_all(read_refs, transaction=actual_transaction)
        snaps = {s.reference.path: s for s in snaps_list if s.exists}

        p1_snap = cast("DocumentSnapshot", snaps.get(p1_ref.path))
        p2_snap = cast("DocumentSnapshot", snaps.get(p2_ref.path))
        p1_data = p1_snap.to_dict() if p1_snap else {}
        p2_data = p2_snap.to_dict() if p2_snap else {}

        if match_type == "singles":
            cls._denormalize_singles_players(
                match_data, p1_ref, p1_data or {}, p2_ref, p2_data or {}
            )

        outcome = MatchStatsCalculator.calculate_match_outcome(
            match_data["player1Score"],
            match_data["player2Score"],
            side1_ids,
            side2_ids,
            p1_ref.id,
            p2_ref.id,
        )
        match_data.update(outcome)

        p1_upd, p2_upd = MatchStatsCalculator.calculate_elo_updates(
            outcome["winner"], p1_data, p2_data
        )
        if match_type == "singles" and MatchStatsCalculator.check_upset(
            outcome["winner"], p1_data, p2_data
        ):
            match_data["is_upset"] = True

        # Now perform all writes
        transaction.set(match_ref, match_data)
        transaction.update(p1_ref, p1_upd)
        transaction.update(p2_ref, p2_upd)

        if match_type == "doubles":
            MatchStatsUpdater.update_user_stats_batch(
                transaction,
                match_data.get("team1", []),
                match_data.get("team2", []),
                outcome["winner"],
            )

        if isinstance(transaction, Transaction):
            for uid in outcome.get("winners", []):
                s_ref = (
                    db.collection("users")
                    .document(uid)
                    .collection("stats")
                    .document("lifetime")
                )
                MatchStatsUpdater.update_lifetime_stats_atomic(
                    transaction, uid, True, db, snapshot=snaps.get(s_ref.path)
                )
            for uid in outcome.get("losers", []):
                s_ref = (
                    db.collection("users")
                    .document(uid)
                    .collection("stats")
                    .document("lifetime")
                )
                MatchStatsUpdater.update_lifetime_stats_atomic(
                    transaction, uid, False, db, snapshot=snaps.get(s_ref.path)
                )

        transaction.update(user_ref, {"lastMatchRecordedType": match_type})

        if gid := match_data.get("groupId"):
            transaction.update(
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
            winners=data.get("winners"),
            losers=data.get("losers"),
            participants=data.get("participants"),
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

    @classmethod
    def update_match_score(
        cls, match_id: str, s1_raw: Any, s2_raw: Any, editor_uid: str
    ) -> None:
        """Update a match score with permission checks and stats rollback."""
        from firebase_admin import firestore

        db = firestore.client()
        try:
            s1, s2 = int(s1_raw or 0), int(s2_raw or 0)
        except (ValueError, TypeError):
            raise ValueError("Scores must be valid integers.")

        data = cls.get_by_id(db, match_id)
        if not data:
            raise ValueError("Match not found.")

        cls._check_match_edit_permissions(data, editor_uid, db)
        cls._perform_stats_update(data, s1, s2)
        cls.update(db, match_id, cls._get_match_updates(data, s1, s2))

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

    @classmethod
    def _get_match_updates(
        cls, data: dict[str, Any], s1: int, s2: int
    ) -> dict[str, Any]:
        """Calculate the updates for the match document."""
        m_type = data.get("matchType", "singles")
        side1_ids, side2_ids = cls._get_side_ids(data, m_type)

        s1_id = data.get("team1Id") if m_type == "doubles" else None
        s2_id = data.get("team2Id") if m_type == "doubles" else None

        if m_type != "doubles":
            p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
            s1_id = p1_ref.id if p1_ref else None
            s2_id = p2_ref.id if p2_ref else None

        outcome = MatchStatsCalculator.calculate_match_outcome(
            s1, s2, side1_ids, side2_ids, s1_id, s2_id
        )

        upd = {
            "player1Score": s1,
            "player2Score": s2,
            "winner": outcome["winner"],
            "winnerId": outcome["winnerId"],
            "loserId": outcome["loserId"],
            "winners": outcome["winners"],
            "losers": outcome["losers"],
            "participants": outcome["participants"],
            "status": "COMPLETED",
        }
        return upd

    @staticmethod
    def _get_side_ids(data: dict[str, Any], m_type: str) -> tuple[list[str], list[str]]:
        """Extract user IDs for each side of the match."""
        if m_type == "doubles":
            t1 = [r.id for r in data.get("team1", []) if hasattr(r, "id")]
            t2 = [r.id for r in data.get("team2", []) if hasattr(r, "id")]
            return t1, t2

        p1_ref = data.get("player1Ref")
        p2_ref = data.get("player2Ref")
        return ([p1_ref.id] if p1_ref else []), ([p2_ref.id] if p2_ref else [])
