from __future__ import annotations

from typing import Any

UPSET_THRESHOLD = 0.25


class MatchStatsCalculator:
    """Utility class for match statistics calculations."""

    @staticmethod
    def calculate_match_outcome(  # noqa: PLR0913
        score1: int,
        score2: int,
        side1_ids: list[str],
        side2_ids: list[str],
        side1_id: str | None = None,
        side2_id: str | None = None,
    ) -> dict[str, Any]:
        """Determine winner and return update dict with flat winners/losers lists."""
        winner = "team1" if score1 > score2 else "team2"
        s1_id = side1_id or (side1_ids[0] if side1_ids else "")
        s2_id = side2_id or (side2_ids[0] if side2_ids else "")

        return {
            "winner": winner,
            "winnerId": s1_id if winner == "team1" else s2_id,
            "loserId": s2_id if winner == "team1" else s1_id,
            "winners": side1_ids if winner == "team1" else side2_ids,
            "losers": side2_ids if winner == "team1" else side1_ids,
            "participants": side1_ids + side2_ids,
        }

    @staticmethod
    def calculate_elo_updates(
        winner: str,
        p1_data: dict[str, Any] | None,
        p2_data: dict[str, Any] | None,
        k: int = 32,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Calculate Elo and win/loss updates for both players."""

        def get_stat(data: dict[str, Any] | None, key: str, default: Any) -> Any:
            if data is None:
                return default
            return data.get("stats", {}).get(key, default)

        p1_wins = get_stat(p1_data, "wins", 0)
        p1_losses = get_stat(p1_data, "losses", 0)
        p1_elo = float(get_stat(p1_data, "elo", 1200.0))

        p2_wins = get_stat(p2_data, "wins", 0)
        p2_losses = get_stat(p2_data, "losses", 0)
        p2_elo = float(get_stat(p2_data, "elo", 1200.0))

        expected_p1 = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
        actual_p1 = 1.0 if winner == "team1" else 0.0

        new_p1_elo = p1_elo + k * (actual_p1 - expected_p1)
        new_p2_elo = p2_elo + k * ((1.0 - actual_p1) - (1.0 - expected_p1))

        p1_updates = {
            "stats.wins": p1_wins + (1 if winner == "team1" else 0),
            "stats.losses": p1_losses + (1 if winner == "team2" else 0),
            "stats.elo": new_p1_elo,
        }
        p2_updates = {
            "stats.wins": p2_wins + (1 if winner == "team2" else 0),
            "stats.losses": p2_losses + (1 if winner == "team1" else 0),
            "stats.elo": new_p2_elo,
        }
        return p1_updates, p2_updates

    @staticmethod
    def check_upset(
        winner: str,
        p1_data: dict[str, Any] | None,
        p2_data: dict[str, Any] | None,
    ) -> bool:
        """Check if the match result is an upset based on DUPR ratings."""
        p1_rating = MatchStatsCalculator._extract_rating(p1_data)
        p2_rating = MatchStatsCalculator._extract_rating(p2_data)

        if p1_rating > 0 and p2_rating > 0:
            if winner == "team1" and (p2_rating - p1_rating) >= UPSET_THRESHOLD:
                return True
            if winner == "team2" and (p1_rating - p2_rating) >= UPSET_THRESHOLD:
                return True
        return False

    @staticmethod
    def _extract_rating(data: dict[str, Any] | None) -> float:
        """Extract DUPR rating from user data."""
        if not data:
            return 0.0
        val = data.get("dupr_rating") or data.get("duprRating")
        try:
            return float(val) if val is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
