from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class TeamRepository(BaseRepository):
    """Data access layer for Teams."""

    COLLECTION_NAME = "teams"

    @classmethod
    def get_team_by_members(cls, db: Client, member_ids: list[str]) -> dict[str, Any] | None:
        """Query for an existing team with the exact same member IDs."""
        sorted_ids = sorted(member_ids)
        query = db.collection(cls.COLLECTION_NAME).where(
            filter=firestore.FieldFilter("member_ids", "==", sorted_ids)
        )
        docs = list(query.stream())
        if docs:
            return cls._enrich(docs[0])
        return None

    @classmethod
    def get_teams_by_member(cls, db: Client, member_id: str) -> list[dict[str, Any]]:
        """Fetch all teams that a specific member belongs to."""
        query = db.collection(cls.COLLECTION_NAME).where(
            filter=firestore.FieldFilter("member_ids", "array_contains", member_id)
        )
        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]
