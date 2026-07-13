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
                filter=firestore.FieldFilter("visibility", "==", Visibility.PUBLIC),
            )

            # Simple text search (starts with) if provided
            if query_text:
                group_query = group_query.where(
                    filter=firestore.FieldFilter("name", ">=", query_text),
                ).where(
                    filter=firestore.FieldFilter("name", "<=", query_text + "\uf8ff"),
                )

            for doc in group_query.stream():
                if enriched := cls._enrich(doc):
                    enriched["type"] = "group"
                    results.append(enriched)

        # 2. Search Divisions (nested in Seasons)
        if search_type in ["all", "division"]:
            # Query active seasons
            season_query = db.collection("seasons").where(
                filter=firestore.FieldFilter("status", "==", "ACTIVE"),
            )

            # 1. Collect all valid divisions and their group IDs first
            # to avoid over-fetching
            season_docs_data = []
            group_ids = set()

            for season_doc in season_query.stream():
                season_data = season_doc.to_dict() or {}

                # Filter divisions early
                valid_divisions = []
                divisions = season_data.get("divisions") or []
                for idx, div in enumerate(divisions):
                    if (
                        isinstance(div, dict)
                        and div.get("visibility") == Visibility.PUBLIC
                    ):
                        div_name = str(div.get("name", ""))
                        if query_text and query_text.lower() not in div_name.lower():
                            continue
                        valid_divisions.append((idx, div))

                if valid_divisions:
                    season_docs_data.append(
                        (season_doc.id, season_data, valid_divisions)
                    )
                    if group_id := season_data.get("groupId"):
                        group_ids.add(str(group_id))

            # 2. Batch fetch only the required groups
            from typing import cast

            from google.cloud.firestore_v1.base_document import DocumentSnapshot

            group_cache: dict[str, str] = {}
            if group_ids:
                group_refs = [
                    db.collection("groups").document(gid) for gid in group_ids
                ]
                group_snaps = cast("list[DocumentSnapshot]", db.get_all(group_refs))
                for snap in group_snaps:
                    snap_data = snap.to_dict() or {}
                    group_cache[snap.id] = (
                        str(snap_data.get("name", "Unknown"))
                        if snap.exists
                        else "Unknown"
                    )

            # 3. Assemble results
            for season_id, season_data, valid_divisions in season_docs_data:
                group_id = str(season_data.get("groupId", ""))

                for idx, div in valid_divisions:
                    group_name = (
                        str(group_cache.get(group_id, "Unknown"))
                        if group_id
                        else "Unknown"
                    )
                    participant_ids = div.get("participant_ids") or []
                    results.append(
                        {
                            "id": f"{season_id}_{idx}",
                            "name": div.get("name"),
                            "type": "division",
                            "groupId": group_id,
                            "groupName": group_name,
                            "seasonId": season_id,
                            "divisionIndex": idx,
                            "description": f"Division in {group_name}",
                            "visibility": div.get("visibility"),
                            "join_policy": div.get("join_policy"),
                            "is_featured": div.get("is_featured", False),
                            "member_count": len(participant_ids)
                            if isinstance(participant_ids, list)
                            else 0,
                            "createdAt": season_data.get("createdAt"),
                        },
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
