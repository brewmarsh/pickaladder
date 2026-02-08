"""Service layer for user data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from .helpers import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    @staticmethod
    def smart_display_name(user: dict[str, Any]) -> str:
        """Return a smart display name for a user."""
        return smart_display_name(user)

    @staticmethod
    def update_user_profile(
        db: Client, user_id: str, update_data: dict[str, Any]
    ) -> None:
        """Update a user's profile in Firestore."""
        user_ref = db.collection("users").document(user_id)
        user_ref.update(update_data)

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
    def get_user_matches(db: Client, user_id: str) -> list[DocumentSnapshot]:
        """Fetch all matches involving a user."""
        user_ref = db.collection("users").document(user_id)
        matches_as_p1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", user_ref))
            .stream()
        )
        matches_as_p2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", user_ref))
            .stream()
        )
        matches_as_t1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", user_ref))
            .stream()
        )
        matches_as_t2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", user_ref))
            .stream()
        )

        all_matches = (
            list(matches_as_p1)
            + list(matches_as_p2)
            + list(matches_as_t1)
            + list(matches_as_t2)
        )
        unique_matches = {match.id: match for match in all_matches}.values()
        return list(unique_matches)

    @staticmethod
    def merge_users(db: Client, source_id: str, target_id: str) -> None:
        """Merge two player accounts (Source -> Target). Source is deleted."""
        source_ref = db.collection("users").document(source_id)
        target_ref = db.collection("users").document(target_id)

        current_app.logger.info(f"Merging user {source_id} into {target_id}")

        batch = db.batch()
        UserService._migrate_user_references(db, batch, source_ref, target_ref)
        batch.delete(source_ref)
        batch.commit()
        current_app.logger.info("User merge completed successfully.")

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

            UserService.merge_users(db, ghost_doc.id, real_user_ref.id)
            return True

        except Exception as e:
            current_app.logger.error(f"Error merging ghost user: {e}")
            return False

    @staticmethod
    def _migrate_user_references(
        db: Client, batch: firestore.WriteBatch, source_ref: Any, target_ref: Any
    ) -> None:
        """Orchestrate the migration of all user references from source to target."""
        UserService._migrate_singles_matches(db, batch, source_ref, target_ref)
        UserService._migrate_doubles_matches(db, batch, source_ref, target_ref)
        UserService._migrate_groups(db, batch, source_ref, target_ref)
        UserService._migrate_tournaments(db, batch, source_ref, target_ref)

    @staticmethod
    def _migrate_singles_matches(
        db: Client, batch: firestore.WriteBatch, source_ref: Any, target_ref: Any
    ) -> None:
        """Update singles matches where the user is player 1 or 2."""
        match_updates: dict[str, dict[str, Any]] = {}
        for field in ["player1Ref", "player2Ref"]:
            matches = (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "==", source_ref))
                .stream()
            )
            for match in matches:
                if match.id not in match_updates:
                    match_updates[match.id] = {"ref": match.reference, "data": {}}
                match_updates[match.id]["data"][field] = target_ref

        for update in match_updates.values():
            batch.update(update["ref"], update["data"])

    @staticmethod
    def _migrate_doubles_matches(
        db: Client, batch: firestore.WriteBatch, source_ref: Any, target_ref: Any
    ) -> None:
        """Update doubles matches where the user is in a team array."""
        match_updates: dict[str, dict[str, Any]] = {}
        for field in ["team1", "team2"]:
            matches = (
                db.collection("matches")
                .where(
                    filter=firestore.FieldFilter(field, "array_contains", source_ref)
                )
                .stream()
            )
            for match in matches:
                if match.id not in match_updates:
                    m_data = match.to_dict()
                    if not m_data:
                        continue
                    match_updates[match.id] = {
                        "ref": match.reference,
                        "full_data": m_data,
                        "updates": {},
                    }

                m_data = match_updates[match.id]["full_data"]
                if field in m_data:
                    current_team = m_data[field]
                    new_team = [
                        target_ref if r == source_ref else r for r in current_team
                    ]
                    match_updates[match.id]["updates"][field] = new_team

        for update in match_updates.values():
            if update["updates"]:
                batch.update(update["ref"], update["updates"])

    @staticmethod
    def _migrate_groups(
        db: Client, batch: firestore.WriteBatch, source_ref: Any, target_ref: Any
    ) -> None:
        """Update group memberships."""
        groups = (
            db.collection("groups")
            .where(
                filter=firestore.FieldFilter("members", "array_contains", source_ref)
            )
            .stream()
        )
        for group in groups:
            g_data = group.to_dict()
            if g_data and "members" in g_data:
                current_members = g_data["members"]
                new_members = [
                    target_ref if m == source_ref else m for m in current_members
                ]
                batch.update(group.reference, {"members": new_members})

    @staticmethod
    def _migrate_tournaments(
        db: Client, batch: firestore.WriteBatch, source_ref: Any, target_ref: Any
    ) -> None:
        """Update tournament participant lists and IDs."""
        tournaments = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", source_ref.id
                )
            )
            .stream()
        )

        for tournament in tournaments:
            data = tournament.to_dict()
            if not data:
                continue

            participants = data.get("participants", [])
            updated = False

            for p in participants:
                if not p:
                    continue

                # Check IDs in both formats (ref object or string ID)
                p_ref = p.get("userRef")
                p_uid = p_ref.id if p_ref else p.get("user_id")

                if p_uid == source_ref.id:
                    if "userRef" in p:
                        p["userRef"] = target_ref

                    # Ensure at least one ID field is present and correct
                    if "user_id" in p or "userRef" in p:
                        p["user_id"] = target_ref.id

                    updated = True

            if updated:
                p_ids = data.get("participant_ids", [])
                # Rebuild the simple ID list
                new_p_ids = [
                    target_ref.id if pid == source_ref.id else pid for pid in p_ids
                ]
                batch.update(
                    tournament.reference,
                    {"participants": participants, "participant_ids": new_p_ids},
                )