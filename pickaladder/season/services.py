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
        """Calculate aggregate standings for a specific season."""
        matches = SeasonRepository.get_season_matches(db, season_id)

        # Aggregate by participant
        # { uid: { wins, losses, points_for, points_against } }
        stats: dict[str, dict[str, Any]] = {}

        def ensure_player(uid: str):
            if uid not in stats:
                stats[uid] = {
                    "uid": uid,
                    "wins": 0,
                    "losses": 0,
                    "points_for": 0,
                    "points_against": 0,
                }

        for m in matches:
            if m.get("status") != "COMPLETED":
                continue

            winner_id = m.get("winnerId")
            participants = m.get("participants", [])
            s1 = m.get("player1Score", 0)
            s2 = m.get("player2Score", 0)

            for p in participants:
                ensure_player(p)
                if p == winner_id:
                    stats[p]["wins"] += 1
                else:
                    stats[p]["losses"] += 1

                # Point diff logic (assuming singles for now, doubles needs team mapping)
                # Find if p was p1 or p2
                p1_id = m.get("player1Ref").id if m.get("player1Ref") else None
                if p == p1_id:
                    stats[p]["points_for"] += s1
                    stats[p]["points_against"] += s2
                else:
                    stats[p]["points_for"] += s2
                    stats[p]["points_against"] += s1

        # Convert to list and enrich with user data
        standings = []
        user_ids = list(stats.keys())
        if user_ids:
            user_refs = [db.collection("users").document(uid) for uid in user_ids]
            user_snaps = db.get_all(user_refs)
            user_map = {
                snap.id: (snap.to_dict() | {"id": snap.id})
                for snap in user_snaps if snap.exists
            }

            for uid, s in stats.items():
                s["user"] = user_map.get(uid, {"username": "Unknown"})
                s["point_diff"] = s["points_for"] - s["points_against"]
                total = s["wins"] + s["losses"]
                s["win_percentage"] = (s["wins"] / total * 100) if total > 0 else 0
                standings.append(s)

        # Sort by Wins (desc), then Point Diff (desc)
        standings.sort(key=lambda x: (x["wins"], x["point_diff"]), reverse=True)
        return standings
