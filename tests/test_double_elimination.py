"""Tests for Double Elimination logic and progression."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.tournament.services.tournament_service import TournamentService


class DoubleEliminationTestCase(unittest.TestCase):
    """Test case for DE mapping and finals logic."""

    def setUp(self) -> None:
        self.mock_db = MagicMock()
        self.docs = {}  # type: ignore

        # Mock .collection().document() to return the same mock for the same ID
        def mock_doc(path):
            if path not in self.docs:
                doc = MagicMock()
                doc.id = path
                # For match-fetch-back logic
                snap = MagicMock()
                snap.exists = True
                snap.id = path
                snap.to_dict.return_value = {
                    "round": 1,
                    "bracketPosition": 0,
                    "bracketType": "WINNERS",
                    "tournamentId": "de_tourney",
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
    def test_loser_drop_wr1_to_lr1(self, mock_union, mock_get_t) -> None:
        """Test WR1 loser drops to LR1 with crossover."""
        t_id = "de_tourney"
        match_data = {
            "round": 1,
            "bracketPosition": 0,
            "bracketType": "WINNERS",
            "tournamentId": t_id,
            "loserId": "loser_v1",
        }

        mock_get_t.return_value = {
            "format": "DOUBLE_ELIMINATION",
            "participant_ids": ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"],
        }

        # Mock Loser match query result
        mock_target = MagicMock()
        mock_target.id = "lr1_match_pos3"

        # stream() calls:
        # 1. _advance_winner (Winners check)
        # 2. _push_to_finals (Finals check)
        # 3. _drop_loser (Losers check)
        self.mock_query.stream.side_effect = [[], [], [mock_target]]

        TournamentService.handle_match_completion(
            self.mock_db,
            t_id,
            match_data,
            "winner_1",
        )

        # Verify update call on the LOSER match
        self.mock_query.document("lr1_match_pos3").update.assert_called()
        args = self.mock_query.document("lr1_match_pos3").update.call_args[0][0]
        assert args["player2Ref"].id == "loser_v1"

    @patch(
        "pickaladder.tournament.services.tournament_service.TournamentService.get_tournament",
    )
    @patch("firebase_admin.firestore.ArrayUnion", return_value=["val"])
    def test_push_to_finals(self, mock_union, mock_get_t) -> None:
        """Test bracket winners populate Finals correctly."""
        t_id = "de_tourney"
        match_data = {
            "round": 3,  # Winners final
            "bracketPosition": 0,
            "bracketType": "WINNERS",
            "tournamentId": t_id,
            "loserId": "l",
        }

        mock_get_t.return_value = {
            "format": "DOUBLE_ELIMINATION",
            "participant_ids": ["p1", "p2", "p3", "p4"],
        }

        # Stream side effect:
        # 1. _advance_winner (Winners next round) -> []
        # 2. _push_to_finals (Finals match) -> [finals_match]
        finals_match = MagicMock()
        finals_match.id = "finals_match"
        self.mock_query.stream.side_effect = [[], [finals_match], []]

        TournamentService.handle_match_completion(
            self.mock_db,
            t_id,
            match_data,
            "w_final",
        )

        self.mock_query.document("finals_match").update.assert_called()
        args = self.mock_query.document("finals_match").update.call_args[0][0]
        assert args["player1Ref"].id == "w_final"


if __name__ == "__main__":
    unittest.main()
