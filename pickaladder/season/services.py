"""Service layer for season operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

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

    @staticmethod
    def join_season_division(
        db: Client,
        season_id: str,
        division_index: int,
        user_id: str,
    ) -> None:
        """Add a user to a division, and ensure they are in the parent group."""
        from pickaladder.group.repository import GroupRepository

        season = SeasonRepository.get_by_id(db, season_id)
        if not season:
            msg = "Season not found"
            raise ValueError(msg)

        group_id = season.get("groupId")
        if not group_id:
            msg = "Season has no associated group"
            raise ValueError(msg)

        divisions = season.get("divisions", [])
        if division_index >= len(divisions):
            msg = "Invalid division index"
            raise ValueError(msg)

        # 1. Add to parent group
        user_ref = db.collection("users").document(user_id)
        GroupRepository.update(
            db,
            group_id,
            {"members": firestore.ArrayUnion([user_ref])},
        )

        # 2. Add to division participant_ids
        # Firestore doesn't support updating a specific index in an array easily.
        # We have to update the entire 'divisions' array.
        if "participant_ids" not in divisions[division_index]:
            divisions[division_index]["participant_ids"] = []

        if user_id not in divisions[division_index]["participant_ids"]:
            divisions[division_index]["participant_ids"].append(user_id)
            SeasonRepository.update(db, season_id, {"divisions": divisions})


class SeasonStandingsService:
    """Calculates and aggregates standings for a season."""

    @staticmethod
    def get_season_standings(
        db: Client,
        season_id: str,
        division_index: int | None = None,
    ) -> list[dict[str, Any]]:
        """Calculate standings for a specific season/division using USAP hierarchy."""
        from pickaladder.core.ranking.aggregator import StandingAggregator
        from pickaladder.group.services.group_service import GroupService

        season = SeasonRepository.get_by_id(db, season_id)
        if not season:
            return []

        matches = SeasonRepository.get_season_matches(db, season_id)

        # 1. Determine participant pool
        # If division_index is provided, only include those participants
        if (
            division_index is not None
            and "divisions" in season
            and len(season["divisions"]) > division_index
        ):
            participant_ids = season["divisions"][division_index].get(
                "participant_ids",
                [],
            )
        else:
            # Fallback to all group members
            group_data = GroupService.get_group_details(db, season["groupId"], "")
            if not group_data:
                return []
            participant_ids = [
                p["user"]["id"] for p in group_data.get("participants", [])
            ]

        # 2. Use Aggregator
        standings = StandingAggregator.aggregate(participant_ids, matches)

        # 3. Enrich with user data (we fetch from group service for simplicity)
        group_data = GroupService.get_group_details(db, season["groupId"], "")
        user_map = {
            p["user"]["id"]: p["user"] for p in group_data.get("participants", [])
        }

        for s in standings:
            s["user"] = user_map.get(s["uid"], {"username": "Unknown"})

        return standings


class SeasonFinalizationService:
    """Handles season closure and player movements."""

    @staticmethod
    def calculate_movements(db: Client, season_id: str) -> dict[str, Any]:
        """
        Calculate who moves up and down based on standings and season rules.
        Returns a dict with 'promoted', 'relegated', and 'retained' lists.
        """
        season = SeasonRepository.get_by_id(db, season_id)
        if not season:
            msg = "Season not found"
            raise ValueError(msg)

        standings = SeasonStandingsService.get_season_standings(db, season_id)
        rules = season.get("movementRules", {"promotionCount": 0, "relegationCount": 0})

        prom_count = rules.get("promotionCount", 0)
        rel_count = rules.get("relegationCount", 0)

        # Sort is already handled by aggregator (Matches > H2H > PD)
        # Promoted: Top X
        promoted = standings[:prom_count] if prom_count > 0 else []

        # Relegated: Bottom Y
        relegated = standings[-rel_count:] if rel_count > 0 else []

        # Retained: The rest
        promoted_uids = {p["uid"] for p in promoted}
        relegated_uids = {p["uid"] for p in relegated}

        retained = [
            p
            for p in standings
            if p["uid"] not in promoted_uids and p["uid"] not in relegated_uids
        ]

        return {"promoted": promoted, "relegated": relegated, "retained": retained}

    @staticmethod
    def finalize_season(db: Client, season_id: str) -> None:
        """Lock the season and capture final standings snapshot."""
        from pickaladder.core.activity.models import ActivityType
        from pickaladder.core.activity.services import ActivityService

        season = SeasonRepository.get_by_id(db, season_id)
        standings = SeasonStandingsService.get_season_standings(db, season_id)

        # Store snapshot directly on the season document for easy historical access
        SeasonRepository.update(
            db,
            season_id,
            {"status": "COMPLETED", "finalStandings": standings},
        )

        # Log community activity
        ActivityService.log_activity(
            db,
            "",  # System level / generic actor if needed
            ActivityType.SEASON_FINALIZED,
            {
                "seasonId": season_id,
                "seasonName": season.get("name") if season else "Unknown Season",
            },
        )

    @staticmethod
    def apply_movements(db: Client, old_season_id: str) -> list[dict[str, Any]]:
        """
        Calculate movements and return a suggested divisions list for the NEXT season.
        Logic:
        - Div 1 promoted -> stay in Div 1.
        - Div 2 promoted -> move to Div 1.
        - Div 1 relegated -> move to Div 2.
        - etc.
        """
        old_season = SeasonRepository.get_by_id(db, old_season_id)
        if not old_season:
            return []

        # Currently we only have one 'pool' in get_season_standings.
        # In a real multi-division setup, we'd iterate through each division.
        # For MVP: We assume one division and movements are just lists.

        movements = SeasonFinalizationService.calculate_movements(db, old_season_id)

        # Suggested new divisions (for now, just reconstructing the pool)
        # If we had 3 divisions, this logic would be more complex.
        # We'll return the flattened suggestions for the next creation form.

        return {  # type: ignore
            "suggested_participants": [
                p["uid"] for p in movements["promoted"] + movements["retained"]
            ],
            "relegated_participants": [p["uid"] for p in movements["relegated"]],
        }
