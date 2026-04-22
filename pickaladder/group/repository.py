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
