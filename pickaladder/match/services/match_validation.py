from __future__ import annotations

from typing import TYPE_CHECKING

from .query import MatchQueryService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

    from pickaladder.match.models import MatchSubmission


class MatchValidationService:
    @staticmethod
    def validate_submission(db: Client, sub: MatchSubmission, user_id: str) -> None:
        """Validate that all players are valid candidates."""
        MatchValidationService._check_score_bounds(sub)
        MatchValidationService._check_duplicate_players(sub)
        MatchValidationService._check_player_validity(db, sub, user_id)

    @staticmethod
    def _check_score_bounds(sub: MatchSubmission) -> None:
        """Ensure scores are non-negative."""
        if sub.score_p1 < 0 or sub.score_p2 < 0:
            msg = "Scores must be non-negative."
            raise ValueError(msg)

    @staticmethod
    def _check_duplicate_players(sub: MatchSubmission) -> None:
        """Ensure no duplicate players are selected."""
        players: list[str | None] = [sub.player_1_id, sub.player_2_id]
        if sub.match_type == "doubles":
            players.extend([sub.partner_id, sub.opponent_2_id])

        # Filter out None values and check for uniqueness
        valid_players = [p for p in players if p is not None]
        if len(valid_players) != len(set(valid_players)):
            msg = "Duplicate players selected."
            raise ValueError(msg)

    @staticmethod
    def _check_player_validity(db: Client, sub: MatchSubmission, user_id: str) -> None:
        """Validate that all players are valid candidates."""
        cands = MatchQueryService.get_candidate_player_ids(
            db,
            user_id,
            sub.group_id,
            sub.tournament_id,
            sub.session_id,
        )
        p1_cands = MatchQueryService.get_candidate_player_ids(
            db,
            user_id,
            sub.group_id,
            sub.tournament_id,
            sub.session_id,
            True,
        )

        if sub.player_1_id not in p1_cands:
            msg = "Invalid Team 1 Player 1 selected."
            raise ValueError(msg)
        if sub.player_2_id not in cands:
            msg = "Invalid Opponent 1 selected."
            raise ValueError(msg)
        if sub.match_type == "doubles":
            if sub.partner_id not in cands:
                msg = "Invalid Partner selected."
                raise ValueError(msg)
            if sub.opponent_2_id not in cands:
                msg = "Invalid Opponent 2 selected."
                raise ValueError(msg)
