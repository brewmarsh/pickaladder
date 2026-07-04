"""Repository for season data access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class SeasonRepository(BaseRepository):
    """Handles Firestore operations for Seasons."""

    COLLECTION_NAME = "seasons"

    @classmethod
    def get_by_group(cls, db: Client, group_id: str) -> list[dict[str, Any]]:
        """Fetch all seasons belonging to a specific group."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("groupId", "==", group_id))
            .order_by("startDate", direction=firestore.Query.DESCENDING)
        )

        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]

    @classmethod
    def get_season_matches(cls, db: Client, season_id: str) -> list[dict[str, Any]]:
        """Fetch all matches linked to a specific season."""
        query = db.collection("matches").where(
            filter=firestore.FieldFilter("seasonId", "==", season_id),
        )
        return [doc.to_dict() | {"id": doc.id} for doc in query.stream()]  # type: ignore

    @classmethod
    def get_all(cls, db: Client) -> list[dict[str, Any]]:  # type: ignore
        """Fetch all seasons globally."""
        docs = db.collection(cls.COLLECTION_NAME).stream()
        return [enriched for doc in docs if (enriched := cls._enrich(doc)) is not None]
