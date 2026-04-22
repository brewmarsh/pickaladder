import pytest
from flask import g

def test_api_user_teams(client, auth, mock_db):
    """Test the /team/api/user-teams endpoint."""
    auth.login()
    uid = auth.user_id
    
    # Create a named team for the user
    mock_db.collection("teams").add({
        "name": "Team A",
        "type": "named",
        "member_ids": [uid, "other_user"],
        "isActive": True
    }, "team_a")
    
    # Create a pairing team (should be ignored)
    mock_db.collection("teams").add({
        "name": "Pairing",
        "type": "pairing",
        "member_ids": [uid, "other_user"],
        "isActive": True
    }, "team_pairing")

    response = client.get('/team/api/user-teams')
    assert response.status_code == 200
    data = response.get_json()
    assert "teams" in data
    assert len(data["teams"]) == 1
    assert data["teams"][0]["id"] == "team_a"
    assert data["teams"][0]["name"] == "Team A"

def test_api_team_roster(client, auth, mock_db):
    """Test the /team/api/<team_id>/roster endpoint."""
    auth.login()
    uid = auth.user_id
    
    # Create users
    mock_db.collection("users").add({"name": "User 1"}, uid)
    mock_db.collection("users").add({"name": "User 2"}, "u2")
    
    # Create team
    mock_db.collection("teams").add({
        "name": "Team A",
        "type": "named",
        "member_ids": [uid, "u2"],
        "members": [mock_db.collection("users").document(uid), mock_db.collection("users").document("u2")],
        "isActive": True
    }, "team_a")
    
    response = client.get('/team/api/team_a/roster')
    assert response.status_code == 200
    data = response.get_json()
    assert "members" in data
    assert len(data["members"]) == 2
    
    member_ids = [m["id"] for m in data["members"]]
    assert uid in member_ids
    assert "u2" in member_ids

def test_api_team_roster_unauthorized(client, auth, mock_db):
    """Test that unauthorized users cannot view roster."""
    auth.login()
    
    # Create team NOT containing the user
    mock_db.collection("teams").add({
        "name": "Team B",
        "type": "named",
        "member_ids": ["u2", "u3"],
        "isActive": True
    }, "team_b")
    
    response = client.get('/team/api/team_b/roster')
    assert response.status_code == 403
