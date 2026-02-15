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
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentGenerator:
    """Utility class for generating tournament matches."""

    MIN_PARTICIPANTS = 2

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate round-robin pairings using the Circle Method."""
        if len(participant_ids) < TournamentGenerator.MIN_PARTICIPANTS:
            return []

        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append(None)  # type: ignore # Bye

        num_participants = len(ids)
        num_rounds = num_participants - 1
        matches = []
        db = firestore.client()

        for _ in range(num_rounds):
            for i in range(num_participants // 2):
                p1 = ids[i]
                p2 = ids[num_participants - 1 - i]
                if p1 is not None and p2 is not None:
                    matches.append({
                        "player1Ref": db.collection("users").document(p1),
                        "player2Ref": db.collection("users").document(p2),
                        "matchType": "singles",
                        "status": "PENDING",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                    })
            # Rotate ids: keep the first element fixed, rotate others
            ids = [ids[0], ids[-1]] + ids[1:-1]

        return matches


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
                participants.append({
                    "user": u_data,
                    "status": obj.get("status", "pending"),
                    "display_name": smart_display_name(u_data),
                    "team_name": obj.get("team_name"),
                })
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
            .where(filter=firestore.FieldFilter("participant_ids", "array_contains", user_uid))
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
                        data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                    results[doc.id] = data

        return list(results.values())

    @staticmethod
    def upload_tournament_banner(tournament_id: str, banner_file: Any) -> str | None:
        """Upload tournament banner to Cloud Storage."""
        if not banner_file or not getattr(banner_file, "filename", None):
            return None

        import os
        import tempfile
        from firebase_admin import storage
        from werkzeug.utils import secure_filename

        filename = secure_filename(banner_file.filename or f"banner_{tournament_id}.jpg")
        bucket = storage.bucket()
        blob = bucket.blob(f"tournaments/{tournament_id}/{filename}")

        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1]) as tmp:
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

        tournament_payload = {
            "name": data["name"],
            "date": data["date"],
            "location": data["location"],
            "venue_name": data.get("venue_name"),
            "address": data.get("address"),
            "location_data": {
                "name": data.get("venue_name"),
                "address": data.get("address"),
            } if data.get("venue_name") or data.get("address") else None,
            "description": data.get("description"),
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
        """Update tournament details with ownership check."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found.")

        data = cast(dict[str, Any], doc.to_dict())
        owner_id = data.get("organizer_id") or (data.get("ownerRef").id if data.get("ownerRef") else None)

        if owner_id != user_uid:
            raise PermissionError("Unauthorized.")

        if "start_date" in update_data:
            update_data["date"] = update_data["start_date"]

        if "venue_name" in update_data or "address" in update_data:
            v_name = update_data.get("venue_name") or data.get("venue_name")
            addr = update_data.get("address") or data.get("address")
            update_data["location_data"] = {"name": v_name, "address": addr}

        if "matchType" in update_data:
            matches = db.collection("matches").where(
                filter=firestore.FieldFilter("tournamentId", "==", tournament_id)
            ).limit(1).stream()
            if any(matches):
                del update_data["matchType"]

        ref.update(update_data)

    @staticmethod
    def invite_player(
        tournament_id: str, user_uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player using a batch for atomicity."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        invited_ref = db.collection("users").document(invited_uid)
        
        batch = db.batch()
        batch.update(ref, {
            "participants": firestore.ArrayUnion([{"userRef": invited_ref, "status": "pending", "team_name": None}]),
            "participant_ids": firestore.ArrayUnion([invited_uid]),
        })
        batch.commit()

    @staticmethod
    def invite_group(
        tournament_id: str, group_id: str, user_uid: str, db: Client | None = None
    ) -> int:
        """Invite all members of a group using atomic batching."""
        if db is None:
            db = firestore.client()

        t_ref = db.collection("tournaments").document(tournament_id)
        t_data = cast(dict[str, Any], t_ref.get().to_dict())
        
        member_refs = TournamentService._validate_group_invite(db, t_data, group_id, user_uid)
        current_ids = set(t_data.get("participant_ids", []))
        member_docs = cast(list[Any], db.get_all(member_refs))

        new_parts, new_ids = TournamentService._prepare_group_invites(member_docs, current_ids)

        if new_parts:
            batch = db.batch()
            batch.update(t_ref, {
                "participants": firestore.ArrayUnion(new_parts),
                "participant_ids": firestore.ArrayUnion(new_ids),
            })
            batch.commit()
        return len(new_parts)

    @staticmethod
    def delete_tournament(tournament_id: str, user_uid: str, db: Client | None = None) -> None:
        """Delete a tournament and its associated data."""
        if db is None:
            db = firestore.client()
        db.collection("tournaments").document(tournament_id).delete()

    # ... (remaining service methods for acceptance and registration continue here)