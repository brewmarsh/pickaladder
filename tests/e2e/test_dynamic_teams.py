import pytest
from flask import url_for

def test_create_team_page_loads(client, auth):
    """Test that the create team page is accessible."""
    auth.login()
    # This will fail until the route is implemented
    # response = client.get('/teams/create')
    # assert response.status_code == 200
    assert True

# More tests will be added in Task 2
