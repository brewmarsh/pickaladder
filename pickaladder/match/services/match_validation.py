from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .query import MatchQueryService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from pickaladder.match.models import MatchSubmission

class MatchValidationService:
    @staticmethod
    def validate_submission(db: Client, sub: MatchSubmission, user_id: str) -> None:
        """Validate that all players are valid candidates."""
        cands = MatchQueryService.get_candidate_player_ids(
            db, user_id, sub.group_id, sub.tournament_id
        )
        p1_cands = MatchQueryService.get_candidate_player_ids(
            db, user_id, sub.group_id, sub.tournament_id, True
        )

        if sub.player_1_id not in p1_cands:
            raise ValueError("Invalid Team 1 Player 1 selected.")
        if sub.player_2_id not in cands:
            raise ValueError("Invalid Opponent 1 selected.")
        if sub.match_type == "doubles":
            if sub.partner_id not in cands:
                raise ValueError("Invalid Partner selected.")
            if sub.opponent_2_id not in cands:
                raise ValueError("Invalid Opponent 2 selected.")
