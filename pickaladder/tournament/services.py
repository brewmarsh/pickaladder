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
    """Utility class for generating tournament matches."""

    MIN_PARTICIPANTS = 2

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate round robin pairings using the circle method."""
        if len(participant_ids) < TournamentGenerator.MIN_PARTICIPANTS:
            return []

        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append("BYE")

        num_participants = len(ids)
        num_rounds = num_participants - 1
        matches = []

        for _ in range(num_rounds):
            for i in range(num_participants // 2):
                p1 = ids[i]
                p2 = ids[num_participants - 1 - i]
                if p1 != "BYE" and p2 != "BYE":
                    # Correctly format for Firestore match documents
                    matches.append({
                        "player1Ref": firestore.client().collection("users").document(p1),
                        "player2Ref": firestore.client().collection("users").document(p2),
                        "participants": [p1, p2],
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
    def _upload_banner(tournament_id: str, banner_file: Any) -> str | None:
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
            "date": data.get("start_date") or data.get("date"),
            "location": data.get("venue_name") or data.get("location"),
            "address": data.get("address"),
            "format": data.get("format"),
            "description": data.get("description"),
            "matchType": data.get("match_type", "singles").lower(),
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

        # Compatibility mappings
        if "start_date" in update_data:
            update_data["date"] = update_data["start_date"]

        if "match_type" in update_data:
            update_data["mode"] = update_data["match_type"]
            update_data["matchType"] = update_data["match_type"].lower()

        # Integrity check: don't allow matchType change if matches exist
        if "matchType" in update_data:
            existing = db.collection("matches").where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id)).limit(1).stream()
            if any(existing):
                del update_data["matchType"]
                if "mode" in update_data:
                    del update_data["mode"]

        ref.update(update_data)

    @staticmethod
    def invite_player(
        tournament_id: str, user_uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        invited_ref = db.collection("users").document(invited_uid)
        ref.update({
            "participants": firestore.ArrayUnion([{"userRef": invited_ref, "status": "pending", "team_name": None}]),
            "participant_ids": firestore.ArrayUnion([invited_uid]),
        })

    @staticmethod
    def invite_group(
        tournament_id: str, group_id: str, user_uid: str, db: Client | None = None
    ) -> int:
        """Invite all members of a group."""
        if db is None:
            db = firestore.client()
        t_ref = db.collection("tournaments").document(tournament_id)
        t_data = cast(Any, t_ref.get()).to_dict()

        from pickaladder.group.services.group_service import GroupService
        group_doc = db.collection("groups").document(group_id).get()
        g_data = group_doc.to_dict()
        
        member_refs = g_data.get("members", [])
        current_ids = set(t_data.get("participant_ids", []))
        
        new_parts = []
        new_ids = []
        for m_ref in member_refs:
            if m_ref.id not in current_ids:
                new_parts.append({"userRef": m_ref, "status": "pending", "team_name": None})
                new_ids.append(m_ref.id)

        if new_parts:
            batch = db.batch()
            batch.update(t_ref, {
                "participants": firestore.ArrayUnion(new_parts),
                "participant_ids": firestore.ArrayUnion(new_ids),
            })
            batch.commit()
        return len(new_parts)

    @staticmethod
    def delete_tournament(tournament_id: str, db: Client | None = None) -> None:
        """Delete a tournament document."""
        if db is None:
            db = firestore.client()
        db.collection("tournaments").document(tournament_id).delete()

    @staticmethod
    def complete_tournament(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> None:
        """Finalize tournament and send results."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        data = cast(dict[str, Any], doc.to_dict())
        owner_id = data.get("organizer_id") or (data.get("ownerRef").id if data.get("ownerRef") else None)

        if owner_id != user_uid:
            raise PermissionError("Only the organizer can complete the tournament.")

        ref.update({"status": "Completed"})
        standings = get_tournament_standings(db, tournament_id, data.get("matchType", "singles"))
        winner = standings[0]["name"] if standings else "No one"
        TournamentService._notify_participants(data, winner, standings)

    @staticmethod
    def _notify_participants(tournament_data: dict[str, Any], winner_name: str, standings: list[dict[str, Any]]) -> None:
        """Internal helper to send result emails."""
        for p in tournament_data.get("participants", []):
            if p and p.get("status") == "accepted":
                try:
                    u_data = p["userRef"].get().to_dict()
                    if u_data and u_data.get("email"):
                        send_email(
                            to=u_data["email"],
                            subject=f"Results: {tournament_data['name']}",
                            template="email/tournament_results.html",
                            user=u_data,
                            tournament=tournament_data,
                            winner_name=winner_name,
                            standings=standings[:3],
                        )
                except Exception as e:
                    logging.error(f"Email failed: {e}")

    # ... (rest of registration/team methods remain same as provided)