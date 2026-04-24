"""Service layer for season operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .repository import SeasonRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class SeasonService:
    """Business logic for seasons."""

    @staticmethod
    def create_season(db: Client, data: dict[str, Any]) -> str:
        """Create a new season."""
        # Simple validation could go here
        return SeasonRepository.create(db, data)

    @staticmethod
    def get_seasons_for_group(db: Client, group_id: str) -> list[dict[str, Any]]:
        """Fetch all seasons for a group."""
        return SeasonRepository.get_by_group(db, group_id)

    @staticmethod
    def get_season(db: Client, season_id: str) -> dict[str, Any] | None:
        """Fetch a single season."""
        return SeasonRepository.get_by_id(db, season_id)

    @staticmethod
    def update_season(db: Client, season_id: str, data: dict[str, Any]) -> None:
        """Update a season."""
        SeasonRepository.update(db, season_id, data)


class SeasonStandingsService:
    """Calculates and aggregates standings for a season."""

    @staticmethod
    def get_season_standings(db: Client, season_id: str) -> list[dict[str, Any]]:
        """Calculate aggregate standings for a specific season using USAP hierarchy."""
        from pickaladder.core.ranking.aggregator import StandingAggregator
        from pickaladder.group.services.group_service import GroupService

        season = SeasonRepository.get_by_id(db, season_id)
        if not season:
            return []

        matches = SeasonRepository.get_season_matches(db, season_id)

        # 1. Determine participant pool
        # For now, we use all group members. Later we can segment by division.
        group_data = GroupService.get_group_details(db, season["groupId"], "")
        if not group_data:
            return []

        # participants is a list of resolved profile dicts
        participant_ids = [p["user"]["id"] for p in group_data.get("participants", [])]

        # 2. Use Aggregator
        standings = StandingAggregator.aggregate(participant_ids, matches)

        # 3. Enrich with user data (Aggregator returns basic stats + uid)
        user_map = {
            p["user"]["id"]: p["user"]
            for p in group_data.get("participants", [])
        }

        for s in standings:
            s["user"] = user_map.get(s["uid"], {"username": "Unknown"})

        return standings
