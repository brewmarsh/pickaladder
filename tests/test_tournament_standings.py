import unittest
from unittest.mock import MagicMock, patch

from pickaladder.tournament.utils import sort_and_format_standings


class TournamentStandingsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()

    def test_h2h_tiebreak_two_players(self) -> None:
        # Player A beat Player B
        # Both have 1 win, 1 loss (if they played others)
        # But A beat B directly.
        raw = {
            "playerA": {
                "id": "playerA",
                "wins": 1,
                "losses": 1,
                "point_diff": 5,
                "h2h": {"playerB": 1},
            },
            "playerB": {
                "id": "playerB",
                "wins": 1,
                "losses": 1,
                "point_diff": 10,
                "h2h": {"playerA": 0},
            },
        }

        # Mock enrich_singles_names to just set names
        with patch("pickaladder.tournament.utils._enrich_singles_names") as mock_enrich:

            def side_effect(db, slist) -> None:
                for s in slist:
                    s["name"] = s["id"]

            mock_enrich.side_effect = side_effect

            # We need to update utils.py first for this to work.
            # For now this test will fail as expected.
            sorted_list = sort_and_format_standings(self.db, raw, "singles")

            # Player A should be first because they beat B, even though B has better point_diff
            assert sorted_list[0]["id"] == "playerA"


if __name__ == "__main__":
    unittest.main()
