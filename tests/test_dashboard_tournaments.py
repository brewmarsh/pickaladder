
import pytest
from unittest.mock import MagicMock
from pickaladder.user.utils import UserService
import datetime

@pytest.fixture
def mock_db():
    return MagicMock()

def test_get_active_tournaments(mock_db):
    user_id = "user123"

    # Mock tournament documents
    mock_doc1 = MagicMock()
    mock_doc1.id = "t1"
    mock_doc1.to_dict.return_value = {
        "name": "Active Tournament",
        "status": "Active",
        "participant_ids": [user_id],
        "participants": [{"user_id": user_id, "status": "accepted"}],
        "date": datetime.datetime(2023, 10, 1)
    }

    mock_doc2 = MagicMock()
    mock_doc2.id = "t2"
    mock_doc2.to_dict.return_value = {
        "name": "Scheduled Tournament",
        "status": "Scheduled",
        "participant_ids": [user_id],
        "participants": [{"user_id": user_id, "status": "accepted"}],
        "date": datetime.datetime(2023, 11, 1)
    }

    mock_doc3 = MagicMock()
    mock_doc3.id = "t3"
    mock_doc3.to_dict.return_value = {
        "name": "Pending Tournament",
        "status": "Active",
        "participant_ids": [user_id],
        "participants": [{"user_id": user_id, "status": "pending"}],
        "date": datetime.datetime(2023, 10, 1)
    }

    mock_db.collection.return_value.where.return_value.stream.return_value = [mock_doc1, mock_doc2, mock_doc3]

    active = UserService.get_active_tournaments(mock_db, user_id)

    assert len(active) == 2
    assert active[0]["name"] == "Active Tournament"
    assert active[1]["name"] == "Scheduled Tournament"
    assert "date_display" in active[0]

def test_get_past_tournaments(mock_db, monkeypatch):
    user_id = "user123"

    # Mock tournament documents
    mock_doc = MagicMock()
    mock_doc.id = "t_past"
    mock_doc.to_dict.return_value = {
        "name": "Past Tournament",
        "status": "Completed",
        "participant_ids": [user_id],
        "matchType": "singles",
        "date": datetime.datetime(2023, 1, 1)
    }

    mock_db.collection.return_value.where.return_value.stream.return_value = [mock_doc]

    # Mock get_tournament_standings
    mock_standings = [{"name": "Winner Name", "wins": 5}]
    monkeypatch.setattr("pickaladder.tournament.utils.get_tournament_standings", lambda db, tid, mt: mock_standings)

    past = UserService.get_past_tournaments(mock_db, user_id)

    assert len(past) == 1
    assert past[0]["name"] == "Past Tournament"
    assert past[0]["winner_name"] == "Winner Name"
    assert "date_display" in past[0]
