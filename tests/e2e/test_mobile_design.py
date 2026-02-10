import os

import pytest
from playwright.sync_api import expect


@pytest.fixture
def seeded_data(mock_db):
    # Clear and seed data
    mock_db._data = {}

    # Create a user
    user_id = "testuser"
    user_data = {
        "uid": user_id,
        "username": "testuser",
        "email": "testuser@example.com",
        "name": "Test User",
        "dark_mode": False,
        "isAdmin": True,
        "createdAt": "2023-01-01T00:00:00",
    }
    mock_db.collection("users").document(user_id).set(user_data)

    # Create a group
    group_id = "group1"
    group_data = {
        "name": "Pickleball Pros",
        "description": "A group for pros",
        "ownerRef": mock_db.collection("users").document(user_id),
        "isPublic": True,
        "member_count": 5,
        "members": [mock_db.collection("users").document(user_id)],
    }
    mock_db.collection("groups").document(group_id).set(group_data)

    # Membership
    mock_db.collection("memberships").add(
        {
            "groupRef": mock_db.collection("groups").document(group_id),
            "userRef": mock_db.collection("users").document(user_id),
            "role": "owner",
        }
    )

    # Create a tournament
    tournament_id = "tourney1"
    tournament_data = {
        "name": "Summer Open",
        "date": "2023-07-01",
        "location": "Central Park",
        "matchType": "doubles",
        "ownerRef": mock_db.collection("users").document(user_id),
    }
    mock_db.collection("tournaments").document(tournament_id).set(tournament_data)

    return user_id


def test_mobile_layout(page_with_firebase, app_server, seeded_data):
    page = page_with_firebase
    # 1. Login
    page.goto(f"{app_server}/auth/login")
    page.fill('input[name="email"]', "testuser@example.com")
    page.fill('input[name="password"]', "password123")
    page.click('[data-testid="login-submit"]')

    # Wait for navigation to dashboard
    expect(page).to_have_url(f"{app_server}/user/dashboard")

    # 2. Set viewport to mobile
    page.set_viewport_size({"width": 375, "height": 667})

    # Create directory for screenshots if it doesn't exist
    os.makedirs("verification", exist_ok=True)

    # 3. Check Groups Page
    page.goto(f"{app_server}/group/")
    # Verify grid is 1-column
    groups_grid = page.locator(".groups-grid")
    expect(groups_grid).to_have_css("display", "grid")
    expect(groups_grid).to_have_css("gap", "16px")

    # Check group image height
    img = page.locator(".group-card-img").first
    expect(img).to_have_css("height", "200px")

    page.screenshot(path="verification/mobile_groups.png")

    # 4. Check Tournaments Page
    page.goto(f"{app_server}/tournaments/")
    tournament_grid = page.locator(".tournament-grid")
    expect(tournament_grid).to_have_css("display", "grid")
    expect(tournament_grid).to_have_css("gap", "16px")

    page.screenshot(path="verification/mobile_tournaments.png")

    # 5. Check Community Hub (Search Bar)
    page.goto(f"{app_server}/user/community")
    search_input_group = page.locator(".search-form .input-group")
    expect(search_input_group).to_have_css("flex-direction", "column")
    expect(search_input_group).to_have_css("gap", "10px")

    page.screenshot(path="verification/mobile_community.png")
