from unittest.mock import MagicMock

import pytest

from pickaladder.teams.repository import TeamRepository


@pytest.fixture
def mock_db():
    return MagicMock()


def test_get_team_by_members_pairing_found(mock_db) -> None:
    # Setup mock
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {"type": "pairing", "member_ids": ["u1", "u2"]}
    mock_doc.id = "team_id"

    mock_query = mock_db.collection.return_value.where.return_value
    mock_query.stream.return_value = [mock_doc]

    team = TeamRepository.get_team_by_members(
        mock_db,
        ["u1", "u2"],
        team_type="pairing",
    )

    assert team is not None
    assert team["id"] == "team_id"
    assert team["type"] == "pairing"


def test_get_team_by_members_legacy_found(mock_db) -> None:
    # Setup mock for legacy doc (no type field)
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {"member_ids": ["u1", "u2"]}
    mock_doc.id = "team_id"

    mock_query = mock_db.collection.return_value.where.return_value
    mock_query.stream.return_value = [mock_doc]

    team = TeamRepository.get_team_by_members(
        mock_db,
        ["u1", "u2"],
        team_type="pairing",
    )

    assert team is not None
    assert team["id"] == "team_id"


def test_get_team_by_members_not_found(mock_db) -> None:
    mock_query = mock_db.collection.return_value.where.return_value
    mock_query.stream.return_value = []

    team = TeamRepository.get_team_by_members(mock_db, ["u1", "u2"])
    assert team is None


def test_create_named_team(mock_db) -> None:
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "new_named_team"
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    team_id = TeamRepository.create_named_team(
        mock_db,
        "The Smashers",
        "creator_id",
        ["u1", "u2", "u3"],
    )

    assert team_id == "new_named_team"
    mock_doc_ref.set.assert_called_once()
    args, _kwargs = mock_doc_ref.set.call_args
    data = args[0]
    assert data["name"] == "The Smashers"
    assert data["type"] == "named"
    assert data["member_ids"] == ["u1", "u2", "u3"]
    assert data["createdBy"] == "creator_id"


def test_get_user_named_teams(mock_db) -> None:
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = {
        "type": "named",
        "name": "Team A",
        "member_ids": ["u1", "u2"],
    }
    mock_doc.id = "team_a"

    mock_query = mock_db.collection.return_value.where.return_value.where.return_value
    mock_query.stream.return_value = [mock_doc]

    teams = TeamRepository.get_user_named_teams(mock_db, "u1")

    assert len(teams) == 1
    assert teams[0]["id"] == "team_a"
    assert teams[0]["type"] == "named"
