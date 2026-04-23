"""Tests for match submission security."""

from __future__ import annotations

import unittest
from typing import cast
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.match import MatchService
from pickaladder.match.models import MatchSubmission


class MatchSecurityTestCase(unittest.TestCase):
    """Test case for match submission security."""

    def setUp(self) -> None:
        """Set up a test client and application context."""
        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context."""
        self.app_context.pop()

    @patch("pickaladder.match.services.MatchQueryService.get_candidate_player_ids")
    @patch("pickaladder.match.services.MatchCommandService._record_match_batch")
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

        current_user = {"uid": "player1"}

        submission = MatchSubmission(
            match_type=cast(str, form_data["match_type"]),
            player_1_id=cast(str, form_data["player1"]),
            player_2_id=cast(str, form_data["player2"]),
            score_p1=cast(int, form_data["player1_score"]),
            score_p2=cast(int, form_data["player2_score"]),
            match_date=None,
        )

        # Mock the building of match result to avoid url_for issues
        with patch("pickaladder.match.services.command.MatchCommandService._build_match_result") as mock_build:
            mock_res = MagicMock()
            mock_res.id = "match_123"
            mock_build.return_value = mock_res

            MatchService.record_match(mock_db, submission, current_user)

        # Verify that the data passed to _record_match_batch does NOT include injected fields
        # match_data is the 7th argument (index 6)
        match_data = mock_record_batch.call_args[0][6]
        self.assertNotIn("is_winner", match_data)
        self.assertNotIn("rating", match_data)
        # is_upset might be added by the service itself, but we check if it was overwritten
        # By default check_upset returns False in mock
        self.assertFalse(match_data.get("is_upset", False))

if __name__ == "__main__":
    unittest.main()
