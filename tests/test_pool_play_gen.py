from unittest.mock import MagicMock, patch

import pytest

from pickaladder.tournament.services.generator import TournamentGenerator


@pytest.fixture
def mock_firestore():
    with patch("firebase_admin.firestore.client") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db

        # Mock collection("users").document(id) to return a mock document reference
        def mock_document(path):
            doc = MagicMock()
            doc.path = f"users/{path}"
            return doc

        mock_db.collection.return_value.document.side_effect = mock_document
        yield mock_db


def test_generate_pool_play(mock_firestore):
    participant_ids = [f"p{i}" for i in range(12)]
    pool_count = 3

    pairings = TournamentGenerator.generate_pool_play(participant_ids, pool_count)

    # 12 participants / 3 pools = 4 per pool
    # Each pool of 4 has 4*3/2 = 6 matches
    # Total matches = 3 * 6 = 18
    assert len(pairings) == 18

    # Check pool distribution
    pool_matches = {}
    for match in pairings:
        pid = match["pool_id"]
        pool_matches[pid] = pool_matches.get(pid, 0) + 1
        assert "player1Ref" in match
        assert "player2Ref" in match
        assert match["matchType"] == "singles"
        assert match["status"] == "DRAFT"

    assert len(pool_matches) == 3
    assert set(pool_matches.keys()) == {"A", "B", "C"}
    for pid in pool_matches:
        assert pool_matches[pid] == 6


def test_generate_pool_play_uneven(mock_firestore):
    participant_ids = [f"p{i}" for i in range(10)]
    pool_count = 3

    # 10 participants / 3 pools -> 4, 3, 3
    # Pool 1 (4): 6 matches
    # Pool 2 (3): 3 matches
    # Pool 3 (3): 3 matches
    # Total = 6 + 3 + 3 = 12 matches
    pairings = TournamentGenerator.generate_pool_play(participant_ids, pool_count)
    assert len(pairings) == 12

    pool_matches = {}
    for match in pairings:
        pid = match["pool_id"]
        pool_matches[pid] = pool_matches.get(pid, 0) + 1

    assert pool_matches["A"] == 6
    assert pool_matches["B"] == 3
    assert pool_matches["C"] == 3
