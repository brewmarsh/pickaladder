"""End-to-end test scenarios."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, expect


def test_user_journey(app_server: str, page_with_firebase: Page, mock_db: Any) -> None:
    """Run a complete user journey test."""
    page = page_with_firebase
    base_url = app_server

    # Auto-accept dialogs (alerts, confirms)
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. Account creation (Admin)
    page.goto(f"{base_url}/auth/login")

    if "/auth/install" in page.url:
        page.fill("input[name='username']", "admin")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        page.fill("input[name='name']", "Admin User")
        with page.expect_navigation():
            page.click("button:has-text('Create Admin')")

        expect(page.locator("h2")).to_contain_text("Login")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        with page.expect_navigation():
            page.click("button:has-text('Login')")

    page.click(".btn-edit-gear")
    expect(page.locator("h2:has-text('Settings')")).to_be_visible(timeout=10000)

    # Logout
    page.goto(f"{base_url}/auth/logout")
    expect(page.locator("h2")).to_contain_text("Login")

    # 2. Register User 2
    with page.expect_navigation():
        page.click("text=Register")
    page.wait_for_url("**/auth/register")
    page.fill("input[name='username']", "user2")
    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    page.fill("input[name='confirm_password']", "MyPassword123")
    page.fill("input[name='name']", "User Two")
    page.fill("input[name='dupr_rating']", "3.5")
    with page.expect_navigation():
        page.click("button:has-text('Register')")

    # Now login as User Two
    expect(page.locator("h2")).to_contain_text("Login")
    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    page.click(".btn-edit-gear")
    expect(page.locator("h2:has-text('Settings')")).to_be_visible(timeout=10000)

    # 3. Add Friend (User 2 invites Admin)
    with page.expect_navigation():
        page.click("text=Community")

    page.fill("input[name='search']", "admin")
    with page.expect_navigation():
        page.click("button:has-text('Search')")

    # Click Add Friend for Admin User
    with page.expect_navigation():
        page.click("button:has-text('Add Friend')")
    # After reload, the user should be in the "Sent Friend Requests" section
    expect(page.locator(".requests-section", has_text="admin")).to_be_visible(
        timeout=5000
    )

    # Logout User 2, Login Admin
    page.goto(f"{base_url}/auth/logout")
    expect(page.locator("h2")).to_contain_text("Login")

    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    # Accept Friend Request
    with page.expect_navigation():
        page.click("text=Community")
    expect(page.locator(".incoming-requests-section", has_text="user2")).to_be_visible()
    with page.expect_navigation():
        page.click("button:has-text('Accept')")
    expect(page.locator(".friend-card", has_text="user2")).to_be_visible()

    # 4. Create Group
    with page.expect_navigation():
        page.click("text=Groups")
    with page.expect_navigation():
        page.click("text=Create Group")
    page.fill("input[name='name']", "Pickleballers")
    page.fill("input[name='location']", "Test Court")
    with page.expect_navigation():
        page.click("button:has-text('Create Group')")

    expect(page.locator("h1")).to_contain_text("Pickleballers")

    # 5. Invite Friend to Group
    page.click("summary:has-text('Manage Group & Members')")
    page.select_option("select[name='friend']", value="user2")
    with page.expect_navigation():
        page.click("button:has-text('Invite Friend')")

    # Verify User 2 is added (Logout Admin, Login User 2)
    page.goto(f"{base_url}/auth/logout")

    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    # User 2 should see the group
    with page.expect_navigation():
        page.click("text=Groups")
    expect(page.locator("text=Pickleballers")).to_be_visible()

    # 6. Score Individual Game (User 2 vs Admin)
    page.goto(f"{base_url}/match/record")
    page.select_option("select[name='match_type']", value="singles")
    page.select_option("select[name='player1']", value="user2")
    page.select_option("select[name='player2']", value="admin")
    page.fill("input[name='player1_score']", "11")
    page.fill("input[name='player2_score']", "9")
    with page.expect_navigation():
        page.click("button:has-text('Record Match')")

    # Check flash message
    expect(page.locator(".toast")).to_contain_text(
        "Match recorded successfully"
    )

    # 7. Score Group Game
    with page.expect_navigation():
        page.click("text=Groups")
    with page.expect_navigation():
        page.click("text=Pickleballers")
    with page.expect_navigation():
        page.click("a:has-text('Record a Match')")
    page.select_option("select[name='player1']", value="user2")
    page.select_option("select[name='player2']", value="admin")
    page.fill("input[name='player1_score']", "5")
    page.fill("input[name='player2_score']", "11")
    with page.expect_navigation():
        page.click("button:has-text('Record Match')")

    expect(page.locator("h1")).to_contain_text("Pickleballers")
    expect(page.locator(".toast")).to_contain_text(
        "Match recorded successfully"
    )

    # Check Global Leaderboard (Req: "see the leaderboard")
    with page.expect_navigation():
        page.click("text=Leaderboard")
    expect(page.locator("h1")).to_contain_text("Global Leaderboard")
    # Verify players are listed
    expect(page.locator("td", has_text="Admin User").first).to_be_visible()
    expect(page.locator("td", has_text="User Two").first).to_be_visible()

    # 8. Delete Group Game & 9. Delete Individual Game
    # Needs Admin access
    page.goto(f"{base_url}/auth/logout")

    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    page.goto(f"{base_url}/admin/matches")
    # Delete match involving user2 (first one)
    with page.expect_navigation():
        page.click("button:has-text('Delete')")
    expect(page.locator(".toast")).to_contain_text("Match deleted successfully")

    # Delete second match
    with page.expect_navigation():
        page.click("button:has-text('Delete')")
    expect(page.locator(".toast")).to_contain_text("Match deleted successfully")

    # 10. Update Group Details (Login as Admin - already logged in)
    with page.expect_navigation():
        page.click("text=Groups")
    with page.expect_navigation():
        page.click("text=Pickleballers")
    with page.expect_navigation():
        page.click('[data-testid="group-settings-btn"]')
    page.fill("input[name='location']", "New Court")
    with page.expect_navigation():
        page.click("button:has-text('Update Group')")
    expect(page.locator("text=New Court")).to_be_visible()

    # 11. Invite Email to Group
    page.click("summary:has-text('Manage Group & Members')")
    page.fill("form[action*='group'] input[name='name']", "New Guy")
    page.fill("form[action*='group'] input[name='email']", "newguy@example.com")
    with page.expect_navigation():
        page.click("button:has-text('Send Invite')")
    expect(page.locator(".alert-toast, .alert-success, .toast-body")).to_contain_text(
        "Invitation is being sent"
    )

    # Verify invite token was created
    invites = list(mock_db.collection("group_invites").stream())
    invite_token = None
    for inv in invites:
        if inv.to_dict().get("email") == "newguy@example.com":
            invite_token = inv.id
            break
    assert invite_token is not None  # nosec
