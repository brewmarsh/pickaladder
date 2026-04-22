import pytest
from flask import url_for
from unittest.mock import MagicMock

def test_create_team_page_loads(client, auth, mock_db):
    """Test that the create team page is accessible."""
    auth.login()
    
    # Setup some mock users
    mock_db.collection("users").add({"name": "User 1"}, "u1")
    mock_db.collection("users").add({"name": "User 2"}, "u2")
    
    response = client.get('/teams/create')
    assert response.status_code == 200
    assert b"Create a New Named Team" in response.data
    assert b"User 1" in response.data
    assert b"User 2" in response.data

def test_create_team_submission(client, auth, mock_db):
    """Test submitting the create team form."""
    auth.login()
    uid = auth.user_id # Assuming auth fixture provides this
    
    # Setup some mock users
    mock_db.collection("users").add({"name": "User 1"}, "u1")
    mock_db.collection("users").add({"name": "User 2"}, "u2")
    
    response = client.post('/teams/create', data={
        "name": "The Smashers",
        "members": ["u1", "u2"]
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Check if team was created in mock_db
    teams = list(mock_db.collection("teams").where("type", "==", "named").stream())
    assert len(teams) == 1
    team_data = teams[0].to_dict()
    assert team_data["name"] == "The Smashers"
    assert "u1" in team_data["member_ids"]
    assert "u2" in team_data["member_ids"]
    assert uid in team_data["member_ids"]
