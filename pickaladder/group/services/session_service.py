from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class SessionService(BaseRepository):
    """Service class for session-related operations."""

    COLLECTION_NAME = "sessions"

    @classmethod
    def create_session(
        cls, db: Client, group_id: str, creator_id: str, player_ids: list[str]
    ) -> str:
        """Create a new session and return its ID."""
        from firebase_admin import firestore

        session_data = {
            "groupId": group_id,
            "createdBy": creator_id,
            "playerIds": player_ids,
            "matchIds": [],
            "status": "ACTIVE",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        return cls.create(db, session_data)

    @classmethod
    def get_session(cls, db: Client, session_id: str) -> dict[str, Any] | None:
        """Retrieve a session by its ID."""
        return cls.get_by_id(db, session_id)

    @classmethod
    def add_match_to_session(cls, db: Client, session_id: str, match_id: str) -> None:
        """Link a match to a session."""
        from firebase_admin import firestore

        doc_ref = db.collection(cls.COLLECTION_NAME).document(session_id)
        doc_ref.update(
            {
                "matchIds": firestore.ArrayUnion([match_id]),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )
