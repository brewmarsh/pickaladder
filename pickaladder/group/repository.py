from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class GroupRepository(BaseRepository):
    """Data access layer for Groups."""

    COLLECTION_NAME = "groups"

    @classmethod
    def get_user_groups(cls, db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch all groups the user belongs to."""
        user_ref = db.collection("users").document(user_id)
        query = db.collection(cls.COLLECTION_NAME).where(
            filter=firestore.FieldFilter("members", "array_contains", user_ref)
        )
        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]

    @classmethod
    def validate(
        cls, db: Client, data: dict[str, Any], group_id: str | None = None
    ) -> None:
        """Validate group data for consistency and business rules."""
        name = data.get("name")
        if not name:
            raise ValueError("Group name is required.")

        # Check for unique name among public groups
        if data.get("is_public"):
            query = db.collection(cls.COLLECTION_NAME).where(
                filter=firestore.FieldFilter("name", "==", name)
            ).where(
                filter=firestore.FieldFilter("is_public", "==", True)
            )
            for doc in query.stream():
                if group_id and doc.id == group_id:
                    continue
                raise ValueError(f"A public group named '{name}' already exists.")

    @classmethod
    def create(cls, db: Client, data: dict[str, Any]) -> str:
        """Create a group with validation."""
        cls.validate(db, data)
        return super().create(db, data)

    @classmethod
    def update(cls, db: Client, doc_id: str, data: dict[str, Any]) -> None:
        """Update a group with validation."""
        # For updates, we might only have partial data,
        # so we fetch the full doc to validate
        existing = cls.get_by_id(db, doc_id)
        if not existing:
            raise ValueError(f"Group {doc_id} not found.")

        # Merge existing and update data for validation
        merged = {**existing, **data}
        cls.validate(db, merged, group_id=doc_id)
        super().update(db, doc_id, data)

    @classmethod
    def get_pending_invites(cls, db: Client, group_id: str) -> list[dict[str, Any]]:
        """Fetch all pending invitations for a specific group."""
        invites_ref = db.collection("group_invites")
        query = invites_ref.where(
            filter=firestore.FieldFilter("group_id", "==", group_id)
        ).where(filter=firestore.FieldFilter("used", "==", False))

        pending = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data["token"] = doc.id
            pending.append(data)

        pending.sort(key=lambda x: x.get("createdAt") or 0, reverse=True)
        return pending

    @classmethod
    def get_group_members(
        cls, db: Client, member_refs: list[Any]
    ) -> list[dict[str, Any]]:
        """Fetch full profile data for group members."""
        if not member_refs:
            return []

        snaps = db.get_all(member_refs)
        members = []
        for snap in snaps:
            if snap.exists:
                data = snap.to_dict() or {}
                data["id"] = snap.id
                members.append(data)
        return members
