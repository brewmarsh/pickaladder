from __future__ import annotations
from typing import TYPE_CHECKING, cast
if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from pickaladder.match.models import Match

class MatchBaseQueryService:
    @staticmethod
    def get_match_by_id(db: Client, match_id: str) -> Match | None:
        """Fetch a single match by its ID."""
        match_ref = db.collection("matches").document(match_id)
        match_doc = cast("DocumentSnapshot", match_ref.get())
        if not match_doc.exists:
            return None
        data = cast("Match", match_doc.to_dict() or {})
        data["id"] = match_id
        return data
