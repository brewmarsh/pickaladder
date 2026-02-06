"""Service layer for user data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from .utils import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    @staticmethod
    def get_user_by_id(db: Client, user_id: str) -> dict[str, Any] | None:
        """Fetch a user by their ID."""
        user_ref = db.collection("users").document(user_id)
        user_doc = cast("DocumentSnapshot", user_ref.get())
        if not user_doc.exists:
            return None
        data = user_doc.to_dict()
        if data is None:
            return None
        data["id"] = user_id
        return data

    @staticmethod
    def get_user_friends(
        db: Client, user_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch a user's friends."""
        user_ref = db.collection("users").document(user_id)
        query = user_ref.collection("friends").where(
            filter=firestore.FieldFilter("status", "==", "accepted")
        )
        if limit:
            query = query.limit(limit)

        friends_query = query.stream()
        friend_ids = [f.id for f in friends_query]
        if not friend_ids:
            return []

        refs = [db.collection("users").document(fid) for fid in friend_ids]
        friend_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in friend_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def merge_ghost_user(db: Client, real_user_ref: Any, email: str) -> bool:
        """Check for 'ghost' user with the given email and merge their data."""
        try:
            query = (
                db.collection("users")
                .where(filter=firestore.FieldFilter("email", "==", email.lower()))
                .where(filter=firestore.FieldFilter("is_ghost", "==", True))
                .limit(1)
            )

            ghost_docs = list(query.stream())
            if not ghost_docs:
                return False

            ghost_doc = ghost_docs[0]
            current_app.logger.info(
                f"Merging ghost user {ghost_doc.id} to {real_user_ref.id}"
            )

            batch = db.batch()
            UserService._migrate_ghost_references(
                db, batch, ghost_doc.reference, real_user_ref
            )
            batch.delete(ghost_doc.reference)
            batch.commit()
            current_app.logger.info("Ghost user merge completed successfully.")
            return True

        except Exception as e:
            current_app.logger.error(f"Error merging ghost user: {e}")
            return False

    @staticmethod
    def _migrate_ghost_references(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update all Firestore references from a ghost user to a real user."""
        # 1 & 2: Update Singles Matches
        for field in ["player1Ref", "player2Ref"]:
            for match in (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "==", ghost_ref))
                .stream()
            ):
                batch.update(match.reference, {field: real_user_ref})

        # 3 & 4: Update Doubles Matches
        for field in ["team1", "team2"]:
            for match in (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "array_contains", ghost_ref))
                .stream()
            ):
                batch.update(
                    match.reference, {field: firestore.ArrayRemove([ghost_ref])}
                )
                batch.update(
                    match.reference, {field: firestore.ArrayUnion([real_user_ref])}
                )

        # 5: Update Group Memberships
        groups_query = db.collection("groups").where(
            filter=firestore.FieldFilter("members", "array_contains", ghost_ref)
        )
        for group in groups_query.stream():
            batch.update(
                group.reference, {"members": firestore.ArrayRemove([ghost_ref])}
            )
            batch.update(
                group.reference, {"members": firestore.ArrayUnion([real_user_ref])}
            )

        # 6: Update Tournament Participants
        tournaments_query = db.collection("tournaments").where(
            filter=firestore.FieldFilter(
                "participant_ids", "array_contains", ghost_ref.id
            )
        )
        for tournament in tournaments_query.stream():
            data = tournament.to_dict()
            if not data:
                continue
            participants = data.get("participants", [])
            updated = False
            for p in participants:
                p_uid = None
                if "userRef" in p:
                    p_uid = p["userRef"].id
                elif "user_id" in p:
                    p_uid = p["user_id"]

                if p_uid == ghost_ref.id:
                    # Update both the reference and the flat ID for compatibility
                    if "userRef" in p:
                        p["userRef"] = real_user_ref
                    if "user_id" in p or "userRef" in p:
                        p["user_id"] = real_user_ref.id
                    updated = True

            if updated:
                p_ids = data.get("participant_ids", [])
                new_p_ids = [
                    real_user_ref.id if pid == ghost_ref.id else pid for pid in p_ids
                ]
                batch.update(
                    tournament.reference,
                    {"participants": participants, "participant_ids": new_p_ids},
                )