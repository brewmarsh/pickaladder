from __future__ import annotations

from typing import TYPE_CHECKING

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class SessionService(BaseRepository):
    """Service class for session-related operations."""

    COLLECTION_NAME = "sessions"
    MIN_VERIFICATIONS_FOR_COMPLETION = 2

    @classmethod
    def create_session(
        cls,
        db: Client,
        group_id: str,
        creator_id: str,
        player_ids: list[str],
    ) -> str:
        """Create a new session and return its ID."""
        from firebase_admin import firestore

        session_data = {
            "groupId": group_id,
            "createdBy": creator_id,
            "playerIds": player_ids,
            "matchIds": [],
            "verifiedBy": [],
            "status": "ACTIVE",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        return cls.create(db, session_data)

    @classmethod
    def get_session(cls, db: Client, session_id: str) -> dict[str, object] | None:
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
            },
        )

    @classmethod
    def verify_session(cls, db: Client, session_id: str, user_id: str) -> bool:
        """Add verification from a user to a session."""
        from firebase_admin import firestore

        session = cls.get_session(db, session_id)
        if not session:
            return False

        # Permission check: user must be in playerIds
        if user_id not in session.get("playerIds", []):
            return False

        # Add user to verifiedBy
        doc_ref = db.collection(cls.COLLECTION_NAME).document(session_id)

        verified_by = session.get("verifiedBy", [])
        if user_id in verified_by:
            return True  # Already verified

        doc_ref.update(
            {
                "verifiedBy": firestore.ArrayUnion([user_id]),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
        )

        # Check if we should complete the session (Threshold: 2 unique approvals)
        updated_verified_by = list({*verified_by, user_id})

        if (
            len(updated_verified_by) >= cls.MIN_VERIFICATIONS_FOR_COMPLETION
            and session.get("status") != "COMPLETED"
        ):
            batch = db.batch()
            batch.update(
                doc_ref,
                {"status": "COMPLETED", "updatedAt": firestore.SERVER_TIMESTAMP},
            )

            match_ids = session.get("matchIds", [])
            for m_id in match_ids:
                match_ref = db.collection("matches").document(m_id)
                batch.update(match_ref, {"is_verified": True})

            batch.commit()

        return True
