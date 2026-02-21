"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentGenerator:
    """Utility class for generating tournament pairings and brackets."""

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """
        Generate Round Robin pairings using the Circle Method.
        Supports odd participant counts by adding a "BYE".
        """
        if len(participant_ids) < 2:  # noqa: PLR2004
            return []

        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append("BYE")

        n = len(ids)
        pairings = []
        rounds = n - 1

        db = firestore.client()

        # RESOLVED: Using the advanced rotation logic from the main branch
        for r in range(rounds):
            for i in range(n // 2):
                p1 = ids[i]
                p2 = ids[n - 1 - i]

                if p1 != "BYE" and p2 != "BYE":
                    pairings.append(
                        {
                            "player1Ref": db.collection("users").document(p1),
                            "player2Ref": db.collection("users").document(p2),
                            "status": "PENDING",
                            "round": r + 1,
                            "matchType": "singles",
                            "createdAt": firestore.SERVER_TIMESTAMP,
                        }
                    )

            # Rotate ids (Circle Method: keep first element fixed, rotate others)
            ids = [ids[0]] + [ids[-1]] + ids[1:-1]

        return pairings


class TournamentService:
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def _get_participant_refs(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[DocumentReference]:
        """Extract user references from participant objects."""
        user_refs = []
        for obj in participant_objs:
            if not obj:
                continue
            if obj.get("userRef"):
                user_refs.append(obj["userRef"])
            elif obj.get("user_id"):
                user_refs.append(db.collection("users").document(obj["user_id"]))
        return user_refs

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []

        user_refs = TournamentService._get_participant_refs(db, participant_objs)
        if not user_refs:
            return []

        user_docs = cast(list[Any], db.get_all(user_refs))
        users_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in user_docs
            if doc.exists
        }

        participants = []
        for obj in participant_objs:
            if not obj:
                continue
            user_ref = obj.get("userRef")
            uid = user_ref.id if user_ref else obj.get("user_id")
            if uid and uid in users_map:
                u_data = users_map[uid]
                participants.append(
                    {
                        "user": u_data,
                        "status": obj.get("status", "pending"),
                        "display_name": smart_display_name(u_data),
                        "team_name": obj.get("team_name"),
                    }
                )
        return participants

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_participant_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates."""
        user_ref = db.collection("users").document(user_uid)

        # Source A: Friends
        friends_query = user_ref.collection("friends").stream()
        friend_ids = {doc.id for doc in friends_query}

        # Source B: Groups
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        group_member_ids = set()
        for group_doc in groups_query:
            g_data = group_doc.to_dict()
            if g_data and "members" in g_data:
                for m_ref in g_data["members"]:
                    group_member_ids.add(m_ref.id)

        all_ids = {str(uid) for uid in (friend_ids | group_member_ids)}
        all_ids.discard(str(user_uid))
        final_ids = all_ids - current_participant_ids

        invitable_users = []
        if final_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_ids]
            u_docs = cast(list[Any], db.get_all(u_refs))
            for u_doc in u_docs:
                if u_doc.exists:
                    u_data = u_doc.to_dict()
                    if u_data:
                        u_data["id"] = u_doc.id
                        invitable_users.append(u_data)

        invitable_users.sort(key=lambda u: smart_display_name(u).lower())
        return invitable_users

    @staticmethod
    def list_tournaments(
        user_uid: str, db: Client | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all tournaments for a user."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        owned = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("ownerRef", "==", user_ref))
            .stream()
        )
        participating = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_uid
                )
            )
            .stream()
        )

        results = {}
        for doc in owned:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                raw_date = data.get("start_date") or data.get("date")
                if raw_date and hasattr(raw_date, "to_datetime"):
                    data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                results[doc.id] = data

        for doc in participating:
            if doc.id not in results:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    raw_date = data.get("start_date") or data.get("date")
                    if raw_date and hasattr(raw_date, "to_datetime"):
                        data["date_display"] = raw_date.to_datetime().strftime(
                            "%b %d, %Y"
                        )
                    results[doc.id] = data

        return list(results.values())

    @staticmethod
    def _upload_banner(tournament_id: str, banner_file: Any) -> str | None:
        """Upload tournament banner to Cloud Storage."""
        if not banner_file or not getattr(banner_file, "filename", None):
            return None

        import os
        import tempfile
        from firebase_admin import storage
        from werkzeug.utils import secure_filename

        filename = secure_filename(
            banner_file.filename or f"banner_{tournament_id}.jpg"
        )
        bucket = storage.bucket()
        blob = bucket.blob(f"tournaments/{tournament_id}/{filename}")

        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1], delete=False) as tmp:
            banner_file.save(tmp.name)
            blob.upload_from_filename(tmp.name)

        blob.make_public()
        return str(blob.public_url)

    @staticmethod
    def create_tournament(
        data: dict[str, Any], user_uid: str, db: Client | None = None
    ) -> str:
        """Create a tournament and return its ID."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        # RESOLVED: Adopting the normalized payload from the jules branch
        tournament_payload = {
            "name": data["name"],
            "date": data["date"],
            "start_date": data["date"],  # Normalized compatibility
            "location": data["location"],
            "location_data": data.get("location_data"),
            "description": data.get("description"),
            "format": data.get("format", "ROUND_ROBIN"),
            "matchType": data.get("matchType") or data.get("mode", "SINGLES").lower(),
            "mode": data.get("mode", "SINGLES"),
            "ownerRef": user_ref,
            "organizer_id": user_uid,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_uid],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        _, ref = db.collection("tournaments").add(tournament_payload)
        return str(ref.id)

    @staticmethod
    def update_tournament(
        tournament_id: str,
        user_uid: str,
        update_data: dict[str, Any],
        db: Client | None = None,
    ) -> None:
        """Update tournament details with ownership and state validation."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found.")

        data = cast(dict[str, Any], doc.to_dict())
        if not data:
            raise ValueError("Tournament data is empty.")
        owner_id = data.get("organizer_id") or (data.get("ownerRef") and data["ownerRef"].id)

        if owner_id != user_uid:
            raise PermissionError("Unauthorized.")

        # Normalization
        if "start_date" in update_data:
            update_data["date"] = update_data["start_date"]

        # RESOLVED: Block critical updates if matches exist (Logic from main)
        critical_fields = ["matchType", "mode", "format"]
        if any(field in update_data for field in critical_fields):
            matches = (
                db.collection("matches")
                .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
                .limit(1)
                .stream()
            )
            if any(matches):
                for field in critical_fields:
                    update_data.pop(field, None)
                logging.warning(f"Blocked modification of critical fields for tournament {tournament_id} because matches exist.")

        ref.update(update_data)

    @staticmethod
    def get_tournament_details(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> dict[str, Any] | None:
        """Fetch comprehensive details for the tournament view."""
        if db is None:
            db = firestore.client()
        doc = cast(Any, db.collection("tournaments").document(tournament_id).get())
        if not doc or not doc.exists:
            return None

        data = cast(dict[str, Any], doc.to_dict())
        data["id"] = doc.id

        # Formatting
        raw_date = data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")

        raw_participants = data.get("participants", [])
        participants = TournamentService._resolve_participants(db, raw_participants)

        # Standings & Podium
        standings = get_tournament_standings(
            db, tournament_id, data.get("matchType", "singles")
        )
        podium = standings[:3] if data.get("status") == "Completed" else []

        current_p_ids = {
            str(obj.get("userRef").id if obj.get("userRef") else obj.get("user_id"))
            for obj in raw_participants
            if obj
        }
        invitable = TournamentService._get_invitable_players(
            db, user_uid, current_p_ids
        )

        from pickaladder.user import UserService  # noqa: PLC0415
        user_groups = UserService.get_user_groups(db, user_uid)
        
        team_status = None
        pending_partner_invite = False
        teams_query = db.collection("tournaments").document(tournament_id).collection("teams").stream()
        for t_doc in teams_query:
            t_team = t_doc.to_dict()
            if t_team["p1_uid"] == user_uid or t_team["p2_uid"] == user_uid:
                team_status = t_team["status"]
                if t_team["p2_uid"] == user_uid and t_team["status"] == "PENDING":
                    pending_partner_invite = True
                break

        is_owner = data.get("organizer_id") == user_uid or (
            data.get("ownerRef") and data["ownerRef"].id == user_uid
        )

        return {
            "tournament": data,
            "participants": participants,
            "standings": standings,
            "podium": podium,
            "invitable_users": invitable,
            "user_groups": user_groups,
            "is_owner": is_owner,
            "team_status": team_status,
            "pending_partner_invite": pending_partner_invite,
        }

    @staticmethod
    def invite_player(
        tournament_id: str, user_uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        if db is None:
            db = firestore.client()

        ref = db.collection("tournaments").document(tournament_id)
        invited_ref = db.collection("users").document(invited_uid)

        ref.update(
            {
                "participants": firestore.ArrayUnion(
                    [{"userRef": invited_ref, "status": "pending", "team_name": None}]
                ),
                "participant_ids": firestore.ArrayUnion([invited_uid]),
            }
        )

    @staticmethod
    def delete_tournament(tournament_id: str, db: Client | None = None) -> None:
        """Delete a tournament document."""
        if db is None:
            db = firestore.client()
        # RESOLVED: Added the delete method from the jules branch
        db.collection("tournaments").document(tournament_id).delete()

    @staticmethod
    def register_team(
        tournament_id: str,
        p1_uid: str,
        p2_uid: str | None,
        team_name: str,
        db: Client | None = None,
    ) -> str:
        """Register a doubles team."""
        if db is None:
            db = firestore.client()

        team_data: dict[str, Any] = {
            "p1_uid": p1_uid,
            "p2_uid": p2_uid,
            "team_name": team_name,
            "status": "PENDING",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

        if p2_uid:
            team_id = TeamService.get_or_create_team(db, p1_uid, p2_uid)
            team_data["team_id"] = team_id

        ref = (
            db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .document()
        )
        ref.set(team_data)
        return ref.id

    @staticmethod
    def claim_team_partnership(
        tournament_id: str, team_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Join a placeholder team via an invite link."""
        if db is None:
            db = firestore.client()

        team_ref = (
            db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .document(team_id)
        )
        team_snap = cast(Any, team_ref.get())
        if not team_snap.exists:
            return False

        data = team_snap.to_dict()
        if data.get("p2_uid") or data.get("p1_uid") == user_uid:
            return False

        p1_uid = data["p1_uid"]
        global_team_id = TeamService.get_or_create_team(db, p1_uid, user_uid)

        team_ref.update(
            {"p2_uid": user_uid, "status": "CONFIRMED", "team_id": global_team_id}
        )

        # Sync participants array logic (internal helper assumed)
        return True

    @staticmethod
    def generate_bracket(tournament_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants."""
        if db is None:
            db = firestore.client()

        t_ref = db.collection("tournaments").document(tournament_id)
        t_snap = cast(Any, t_ref.get())
        if not t_snap.exists:
            return []

        t_data = t_snap.to_dict()
        mode = t_data.get("mode", "SINGLES")

        bracket = []
        if mode == "SINGLES":
            participants = [
                p
                for p in t_data.get("participants", [])
                if p.get("status") == "accepted"
            ]
            for p in participants:
                u_ref = p.get("userRef")
                u_data = cast(Any, u_ref.get()).to_dict()
                bracket.append(
                    {
                        "id": u_ref.id,
                        "name": smart_display_name(u_data),
                        "type": "player",
                        "members": [u_ref.id],
                    }
                )
        return bracket