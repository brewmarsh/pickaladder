from unittest.mock import patch


def test_api_user_teams(client, mock_db):
    """Test the /team/api/user-teams endpoint."""
    uid = "test_user"
    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Create a named team for the user
    mock_db.collection("teams").document("team_a").set(
        {
            "name": "Team A",
            "type": "named",
            "member_ids": [uid, "other_user"],
            "isActive": True,
        }
    )

    # Create a pairing team (should be ignored)
    mock_db.collection("teams").document("team_pairing").set(
        {
            "name": "Pairing",
            "type": "pairing",
            "member_ids": [uid, "other_user"],
            "isActive": True,
        }
    )

    with patch(
        "pickaladder.auth.routes.auth.verify_id_token", return_value={"uid": uid}
    ):
        response = client.get("/team/api/user-teams")
        SUCCESS_CODE = 200
        assert response.status_code == SUCCESS_CODE
        data = response.get_json()
        assert "teams" in data
        assert len(data["teams"]) == 1
        assert data["teams"][0]["id"] == "team_a"
        assert data["teams"][0]["name"] == "Team A"


def test_api_team_roster(client, mock_db):
    """Test the /team/api/<team_id>/roster endpoint."""
    uid = "test_user"
    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Create users
    mock_db.collection("users").document(uid).set({"name": "User 1"})
    mock_db.collection("users").document("u2").set({"name": "User 2"})

    # Create team
    mock_db.collection("teams").document("team_a").set(
        {
            "name": "Team A",
            "type": "named",
            "member_ids": [uid, "u2"],
            "members": [
                mock_db.collection("users").document(uid),
                mock_db.collection("users").document("u2"),
            ],
            "isActive": True,
        }
    )

    with patch(
        "pickaladder.auth.routes.auth.verify_id_token", return_value={"uid": uid}
    ):
        response = client.get("/team/api/team_a/roster")
        SUCCESS_CODE = 200
        assert response.status_code == SUCCESS_CODE
        data = response.get_json()
        assert "members" in data
        EXPECTED_MEMBERS = 2
        assert len(data["members"]) == EXPECTED_MEMBERS

        member_ids = [m["id"] for m in data["members"]]
        assert uid in member_ids
        assert "u2" in member_ids


def test_api_team_roster_unauthorized(client, mock_db):
    """Test that unauthorized users cannot view roster."""
    uid = "test_user"
    with client.session_transaction() as sess:
        sess["user_id"] = uid

    # Create team NOT containing the user
    mock_db.collection("teams").document("team_b").set(
        {
            "name": "Team B",
            "type": "named",
            "member_ids": ["u2", "u3"],
            "isActive": True,
        }
    )

    with patch(
        "pickaladder.auth.routes.auth.verify_id_token", return_value={"uid": uid}
    ):
        response = client.get("/team/api/team_b/roster")
        FORBIDDEN_CODE = 403
        assert response.status_code == FORBIDDEN_CODE
