"""Tests for tournament bracket progression logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.tournament.services.tournament_service import TournamentService


class TournamentProgressionTestCase(unittest.TestCase):
    """Test cases for bracket advancement logic."""

    def setUp(self) -> None:
        self.mock_db = MagicMock()
        self.docs = {}

        # Mock .collection().document() to return the same mock for the same ID
        def mock_doc(path):
            if path not in self.docs:
                doc = MagicMock()
                doc.id = path
                # Make .get() return a snapshot with data
                snap = MagicMock()
                snap.exists = True
                snap.id = path
                # Default data for a match
                snap.to_dict.return_value = {
                    "round": 1,
                    "bracketPosition": 0,
                    "bracketType": "WINNERS",
                    "tournamentId": "test_tourney",
                }
                doc.get.return_value = snap
                self.docs[path] = doc
            return self.docs[path]

        self.mock_query = MagicMock()
        self.mock_query.where.return_value = self.mock_query
        self.mock_query.limit.return_value = self.mock_query

        self.mock_db.collection.return_value = self.mock_query
        self.mock_query.document.side_effect = mock_doc

    @patch(
        "pickaladder.tournament.services.tournament_service.TournamentService.get_tournament",
    )
    @patch("firebase_admin.firestore.ArrayUnion", return_value=["val"])
    def test_winner_advancement_p1(self, mock_union, mock_get_t) -> None:
        """Test that winner of match 0 in round 1 moves to next match as player 1."""
        t_id = "test_tourney"
        match_data = {
            "id": "match_1",
            "winnerId": "winner_1",
            "round": 1,
            "bracketPosition": 0,
            "bracketType": "WINNERS",
        }
        winner_uid = "winner_1"

        mock_get_t.return_value = {"format": "SINGLE_ELIMINATION"}

        # Mock query for next match (Round 2, Position 0)
        mock_next_match = MagicMock()
        mock_next_match.id = "next_match_id"
        self.mock_query.stream.return_value = [mock_next_match]

        TournamentService.handle_match_completion(
            self.mock_db,
            t_id,
            match_data,
            winner_uid,
        )

        # Verify update call on the NEXT match
        self.mock_query.document("next_match_id").update.assert_called()
        args = self.mock_query.document("next_match_id").update.call_args[0][0]
        assert "player1Ref" in args
        assert args["player1Ref"].id == winner_uid


if __name__ == "__main__":
    unittest.main()
