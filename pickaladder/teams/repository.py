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
    def get_team_by_members(
        cls, db: Client, member_ids: list[str], team_type: str = "pairing"
    ) -> dict[str, Any] | None:
        """Query for an existing team with the exact same member IDs and type."""
        sorted_ids = sorted(member_ids)
        query = db.collection(cls.COLLECTION_NAME).where(
            filter=firestore.FieldFilter("member_ids", "==", sorted_ids)
        )

        # For pairing, we handle legacy data where 'type' might be missing
        for doc in query.stream():
            data = doc.to_dict() or {}
            if data.get("type", "pairing") == team_type:
                return cls._enrich(doc)
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

    @classmethod
    def get_or_create_team(cls, db: Client, member_ids: list[str]) -> str:
        """Retrieves a team for given members, creating one if it doesn't exist.
        Strictly uses type='pairing'.
        """
        # Use existing method to check for team (handles sorting and legacy type)
        team = cls.get_team_by_members(db, member_ids, team_type="pairing")
        if team:
            return team["id"]

        # If not found, prepare data for creation
        sorted_ids = sorted(member_ids)
        member_refs = [db.collection("users").document(mid) for mid in sorted_ids]
        member_docs = db.get_all(member_refs)

        member_names = []
        for doc in member_docs:
            data = doc.to_dict() or {}
            member_names.append(data.get("name", "Unknown Player"))

        team_name = " & ".join(member_names)

        new_team_data = {
            "member_ids": sorted_ids,
            "members": member_refs,
            "name": team_name,
            "type": "pairing",
            "stats": {"wins": 0, "losses": 0, "elo": 1200},
        }

        return cls.create(db, new_team_data)

    @classmethod
    def create_named_team(
        cls, db: Client, name: str, creator_id: str, member_ids: list[str]
    ) -> str:
        """Create a named team with a roster."""
        sorted_ids = sorted(member_ids)
        member_refs = [db.collection("users").document(mid) for mid in sorted_ids]

        new_team_data = {
            "name": name,
            "type": "named",
            "member_ids": sorted_ids,
            "members": member_refs,
            "createdBy": creator_id,
            "stats": {"wins": 0, "losses": 0, "elo": 1200},
            "isActive": True,
        }
        return cls.create(db, new_team_data)

    @classmethod
    def get_user_named_teams(cls, db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch all named teams that a specific user belongs to."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("type", "==", "named"))
            .where(
                filter=firestore.FieldFilter("member_ids", "array_contains", user_id)
            )
        )
        return [
            enriched
            for doc in query.stream()
            if (enriched := cls._enrich(doc)) is not None
        ]
