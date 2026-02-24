from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pickaladder.match.models import Match


class MatchFormatter:
    """Utility class for match data formatting."""

    @staticmethod
    def apply_common_match_formatting(match_data: Match) -> None:
        """Apply formatting common to all match types."""
        from .query import CLOSE_CALL_THRESHOLD

        match_date = match_data.get("matchDate")
        if isinstance(match_date, datetime.datetime):
            match_data["date"] = match_date.strftime("%b %d")
        else:
            match_data["date"] = "N/A"

        score1 = match_data.get("player1Score", 0)
        score2 = match_data.get("player2Score", 0)
        point_diff = abs(score1 - score2)

        match_data["point_differential"] = point_diff
        match_data["close_call"] = point_diff <= CLOSE_CALL_THRESHOLD

    @staticmethod
    def format_doubles_match_names(match_data: Match, players: dict[str, str]) -> None:
        """Format names and scores for doubles matches."""
        team1_refs = match_data.get("team1", [])
        team2_refs = match_data.get("team2", [])

        t1_names = " & ".join(
            [players.get(getattr(ref, "id", ""), "N/A") for ref in team1_refs]
        )
        t2_names = " & ".join(
            [players.get(getattr(ref, "id", ""), "N/A") for ref in team2_refs]
        )

        s1, s2 = match_data.get("player1Score", 0), match_data.get("player2Score", 0)
        if s1 > s2:
            match_data.update(
                {
                    "winner_name": t1_names,
                    "loser_name": t2_names,
                    "winner_score": s1,
                    "loser_score": s2,
                }
            )
        else:
            match_data.update(
                {
                    "winner_name": t2_names,
                    "loser_name": t1_names,
                    "winner_score": s2,
                    "loser_score": s1,
                }
            )

    @staticmethod
    def format_singles_match_names(match_data: Match, players: dict[str, str]) -> None:
        """Format names and scores for singles matches."""
        if match_data.get("player_1_data") and match_data.get("player_2_data"):
            p1_name = match_data["player_1_data"].get("display_name", "N/A")
            p2_name = match_data["player_2_data"].get("display_name", "N/A")
        else:
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")
            p1_name = players.get(getattr(p1_ref, "id", ""), "N/A") if p1_ref else "N/A"
            p2_name = players.get(getattr(p2_ref, "id", ""), "N/A") if p2_ref else "N/A"

        s1, s2 = match_data.get("player1Score", 0), match_data.get("player2Score", 0)
        if s1 > s2:
            match_data.update(
                {
                    "winner_name": p1_name,
                    "loser_name": p2_name,
                    "winner_score": s1,
                    "loser_score": s2,
                }
            )
        else:
            match_data.update(
                {
                    "winner_name": p2_name,
                    "loser_name": p1_name,
                    "winner_score": s2,
                    "loser_score": s1,
                }
            )
