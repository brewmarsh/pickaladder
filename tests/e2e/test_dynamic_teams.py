from unittest.mock import patch


def test_create_team_page_loads(client, mock_db):
    """Test that the team creation page loads correctly."""
    uid = "test_user"
    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Mock users for selection
    mock_db.collection("users").document("u1").set({"name": "User 1"})
    mock_db.collection("users").document("u2").set({"name": "User 2"})

    with patch("pickaladder.auth.routes.auth.verify_id_token", return_value={"uid": uid}):
        response = client.get('/team/create')
        SUCCESS_CODE = 200
        assert response.status_code == SUCCESS_CODE
        assert b"Create Team" in response.data
        assert b"Team Name" in response.data

def test_create_team_submission(client, mock_db):
    """Test creating a team via form submission."""
    uid = "test_user"
    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Mock users
    mock_db.collection("users").document(uid).set({"name": "Creator"})
    mock_db.collection("users").document("u2").set({"name": "Member 2"})

    form_data = {
        "name": "The Smashers",
        "members": [uid, "u2"]
    }

    with patch("pickaladder.auth.routes.auth.verify_id_token", return_value={"uid": uid}):
        response = client.post('/team/create', data=form_data, follow_redirects=True)
        SUCCESS_CODE = 200
        assert response.status_code == SUCCESS_CODE

        # Verify team created in DB
        teams = list(mock_db.collection("teams").where("name", "==", "The Smashers").stream())
        assert len(teams) == 1
        team_data = teams[0].to_dict()
        assert team_data["type"] == "named"
        assert uid in team_data["member_ids"]
        assert "u2" in team_data["member_ids"]
