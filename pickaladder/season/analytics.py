"""Service layer for analytical operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.season.repository import SeasonRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class AnalyticsService:
    """Extracts and aggregates performance data across entities."""

    @staticmethod
    def get_user_season_history(db: Client, user_id: str) -> list[dict[str, Any]]:
        """
        Retrieves a user's performance stats from all completed seasons.
        Uses snapshots from 'finalStandings' for historical accuracy.
        """
        # 1. Fetch all completed seasons
        # In a high-scale app, we'd query by participant_ids index,
        # but here we scan completed seasons for simplicity.
        all_seasons = SeasonRepository.get_all(db)
        completed_seasons = [s for s in all_seasons if s.get("status") == "COMPLETED"]

        history = []

        for season in completed_seasons:
            standings = season.get("finalStandings", [])

            # Find the user's entry in this season's final snapshot
            user_entry = None
            rank = 0
            for idx, entry in enumerate(standings):
                if entry.get("uid") == user_id:
                    user_entry = entry
                    rank = idx + 1
                    break

            if user_entry:
                history.append(
                    {
                        "seasonId": season["id"],
                        "seasonName": season["name"],
                        "rank": rank,
                        "totalParticipants": len(standings),
                        "wins": user_entry.get("wins", 0),
                        "losses": user_entry.get("losses", 0),
                        "pointDiff": user_entry.get("point_diff", 0),
                        "pointsFor": user_entry.get("points_for", 0),
                        "pointsAgainst": user_entry.get("points_against", 0),
                        "endDate": season.get("endDate"),
                    }
                )

        # Sort by date descending
        return sorted(
            history, key=lambda x: x["endDate"] if x["endDate"] else "", reverse=True
        )

    @staticmethod
    def get_user_achievements(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Calculates career milestones from season history."""
        if not history:
            return []

        achievements = []

        # 1. Career High Rank
        best_rank = min(h["rank"] for h in history)
        achievements.append(
            {
                "type": "rank",
                "label": "Career High",
                "value": f"#{best_rank}",
                "icon": "fa-crown",
            }
        )

        # 2. Total Wins
        total_wins = sum(h["wins"] for h in history)
        if total_wins > 0:
            achievements.append(
                {
                    "type": "wins",
                    "label": "Total Wins",
                    "value": total_wins,
                    "icon": "fa-trophy",
                }
            )

        # 3. Best Win %
        win_rates = []
        for h in history:
            total = h["wins"] + h["losses"]
            if total > 0:
                win_rates.append(h["wins"] / total * 100)

        if win_rates:
            best_rate = max(win_rates)
            achievements.append(
                {
                    "type": "win_rate",
                    "label": "Best Win %",
                    "value": f"{int(best_rate)}%",
                    "icon": "fa-fire",
                }
            )

        return achievements
