"""Security tests for match submission."""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService

if TYPE_CHECKING:
    from pickaladder.user.models import UserSession


class MatchSecurityTestCase(unittest.TestCase):
    """Test case for match submission security."""

    @patch("pickaladder.match.services.MatchService.get_candidate_player_ids")
    @patch("pickaladder.match.services.MatchService._record_match_batch")
    def test_injected_fields_ignored(
        self, mock_record_batch: MagicMock, mock_get_candidates: MagicMock
    ) -> None:
        """Test that injected fields like is_winner are ignored."""
        mock_db = MagicMock()
        # Mock batch
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        mock_get_candidates.return_value = {"player1", "player2"}

        # Simulate form data with injected fields
        form_data = {
            "player1": "player1",
            "player2": "player2",
            "player1_score": 11,
            "player2_score": 5,
            "match_type": "singles",
            "is_winner": "player2",  # Injected
            "is_upset": True,  # Injected
            "rating": 5.0,  # Injected
        }

        current_user = cast("UserSession", {"uid": "player1"})

        submission = MatchSubmission(
            player_1_id=cast(str, form_data["player1"]),
            player_2_id=cast(str, form_data["player2"]),
            score_p1=cast(int, form_data["player1_score"]),
            score_p2=cast(int, form_data["player2_score"]),
            match_type=cast(str, form_data["match_type"]),
        )

        MatchService.record_match(mock_db, submission, current_user)

        # Verify mock_record_batch was called
        self.assertTrue(mock_record_batch.called)

        # Check match_data passed to record_batch
        # _record_match_batch(db, batch, match_ref, p1_ref, p2_ref, ...)
        # index of match_data is 6
        match_data = mock_record_batch.call_args[0][6]

        self.assertNotIn("is_winner", match_data)
        self.assertNotIn("is_upset", match_data)
        self.assertNotIn("rating", match_data)
        self.assertEqual(match_data["player1Score"], 11)
        self.assertEqual(match_data["player2Score"], 5)


if __name__ == "__main__":
    unittest.main()
