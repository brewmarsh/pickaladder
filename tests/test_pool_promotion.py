from unittest.mock import MagicMock, patch

import pytest

from pickaladder.tournament.services.tournament_service import TournamentService


@pytest.fixture
def mock_db():
    with patch("firebase_admin.firestore.client") as mock_client:
        db = MagicMock()
        mock_client.return_value = db
        yield db


def test_promote_pools_to_bracket(mock_db):
    t_id = "t1"
    uid = "owner"

    # Mock tournament data
    mock_t_snap = MagicMock()
    mock_t_snap.exists = True
    mock_t_snap.to_dict.return_value = {
        "organizer_id": uid,
        "pool_count": 2,
        "format": "POOL_PLAY",
        "matchType": "singles",
        "participant_ids": ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"],
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_t_snap

    # Mock standings for Pool A and B
    with patch("pickaladder.tournament.utils.get_tournament_standings") as mock_stands:
        # Pool A standings
        mock_stands.side_effect = [
            [
                {"id": "p1", "wins": 3},
                {"id": "p2", "wins": 2},
                {"id": "p3", "wins": 1},
                {"id": "p4", "wins": 0},
            ],  # Pool A
            [
                {"id": "p5", "wins": 3},
                {"id": "p6", "wins": 2},
                {"id": "p7", "wins": 1},
                {"id": "p8", "wins": 0},
            ],  # Pool B
        ]

        # Promote top 2 from each pool
        # Expected promoted: p1 (Rank 1 Pool A), p5 (Rank 1 Pool B), p2 (Rank 2 Pool A), p6 (Rank 2 Pool B)
        # Seeding logic sorts by rank_in_pool: [p1, p5, p2, p6]

        with patch(
            "pickaladder.tournament.services.generator.TournamentGenerator.generate_single_elimination"
        ) as mock_gen:
            mock_gen.return_value = [{"match": 1}]

            with patch(
                "pickaladder.tournament.services.tournament_service.TournamentService.save_pairings"
            ) as mock_save:
                mock_save.return_value = 1

                res = TournamentService.promote_pools_to_bracket(
                    t_id, uid, 2, db=mock_db
                )

                assert res == 1
                mock_gen.assert_called_once_with(["p1", "p5", "p2", "p6"])
                mock_save.assert_called_once()
