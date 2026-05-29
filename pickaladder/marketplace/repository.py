from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository
from pickaladder.core.constants import Visibility

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class MarketplaceRepository(BaseRepository):
    """Discovery queries for groups and divisions."""

    COLLECTION_NAME = "groups"  # Primarily discover groups

    @classmethod
    def get_featured_groups(cls, db: Client, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch featured groups for the carousel."""
        # Query for is_featured == True AND visibility == PUBLIC
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("visibility", "==", Visibility.PUBLIC))
            .where(filter=firestore.FieldFilter("is_featured", "==", True))
            .limit(limit)
        )

        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]

    @classmethod
    def search_marketplace(
        cls,
        db: Client,
        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search and filter public groups and divisions."""
        results: list[dict[str, Any]] = []
        search_type = filters.get("type", "all") if filters else "all"

        # 1. Search Groups
        if search_type in ["all", "group"]:
            group_query = db.collection("groups").where(
                filter=firestore.FieldFilter("visibility", "==", Visibility.PUBLIC)
            )

            # Simple text search (starts with) if provided
            if query_text:
                group_query = group_query.where(
                    filter=firestore.FieldFilter("name", ">=", query_text)
                ).where(
                    filter=firestore.FieldFilter("name", "<=", query_text + "\uf8ff")
                )

            for doc in group_query.stream():
                if enriched := cls._enrich(doc):
                    enriched["type"] = "group"
                    results.append(enriched)

        # 2. Search Divisions (nested in Seasons)
        if search_type in ["all", "division"]:
            # Query active seasons
            season_query = db.collection("seasons").where(
                filter=firestore.FieldFilter("status", "==", "ACTIVE")
            )

            group_cache: dict[str, str] = {}

            for season_doc in season_query.stream():
                season_data = season_doc.to_dict()
                season_id = season_doc.id
                group_id = season_data.get("groupId")
                divisions = season_data.get("divisions", [])

                for idx, div in enumerate(divisions):
                    if div.get("visibility") == Visibility.PUBLIC:
                        # Match query_text if provided (case-insensitive in memory)
                        if (
                            query_text
                            and query_text.lower() not in div.get("name", "").lower()
                        ):
                            continue

                        if group_id not in group_cache:
                            g_doc = db.collection("groups").document(group_id).get()
                            group_cache[group_id] = (
                                g_doc.to_dict().get("name")
                                if g_doc.exists
                                else "Unknown"
                            )

                        results.append(
                            {
                                "id": f"{season_id}_{idx}",
                                "name": div.get("name"),
                                "type": "division",
                                "groupId": group_id,
                                "groupName": group_cache[group_id],
                                "seasonId": season_id,
                                "divisionIndex": idx,
                                "description": f"Division in {group_cache[group_id]}",
                                "visibility": div.get("visibility"),
                                "join_policy": div.get("join_policy"),
                                "is_featured": div.get("is_featured", False),
                                "member_count": len(div.get("participant_ids", [])),
                                "createdAt": season_data.get("createdAt"),
                            }
                        )

        # In-memory sorting
        if filters:
            if filters.get("sort") == "popular":
                results.sort(
                    key=lambda x: (
                        len(x.get("members", []))
                        if x["type"] == "group"
                        else x.get("member_count", 0)
                    ),
                    reverse=True,
                )
            elif filters.get("sort") == "new":
                results.sort(key=lambda x: str(x.get("createdAt", "")), reverse=True)

        return results
