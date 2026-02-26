from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

    from pickaladder.match.models import Match


class MatchBaseQueryService(BaseRepository):
    COLLECTION_NAME = "matches"

    @classmethod
    def get_match_by_id(cls, db: Client, match_id: str) -> Match | None:
        """Fetch a single match by its ID."""
        data = cls.get_by_id(db, match_id)
        return cast("Match", data) if data else None
