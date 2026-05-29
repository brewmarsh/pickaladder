from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class MembershipRequestRepository(BaseRepository):
    """Data access layer for Group/Division membership requests."""

    COLLECTION_NAME = "membership_requests"

    @classmethod
    def get_pending_for_group(cls, db: Client, group_id: str) -> list[dict[str, object]]:
        """Fetch all pending requests for a specific group."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("groupId", "==", group_id))
            .where(filter=firestore.FieldFilter("status", "==", "PENDING"))
        )
        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]

    @classmethod
    def get_user_request_for_group(
        cls, db: Client, group_id: str, user_id: str
    ) -> dict[str, object] | None:
        """Fetch a specific user's request for a group."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("groupId", "==", group_id))
            .where(filter=firestore.FieldFilter("userId", "==", user_id))
            .limit(1)
        )
        results = list(query.stream())
        if not results:
            return None
        return cls._enrich(results[0])

    @classmethod
    def create_request(
        cls, db: Client, group_id: str, user_id: str, message: str | None = None
    ) -> str:
        """Create a new membership request."""
        data = {
            "groupId": group_id,
            "userId": user_id,
            "status": "PENDING",
            "message": message or "",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        return cls.create(db, data)

    @classmethod
    def update_status(cls, db: Client, request_id: str, status: str) -> None:
        """Update the status of a request."""
        cls.update(
            db,
            request_id,
            {"status": status, "updatedAt": firestore.SERVER_TIMESTAMP},
        )
