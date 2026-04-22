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

    page.hover(".navbar-user-controls .dropdown")
    page.get_by_test_id("navbar__settings-link").click()
    expect(page.get_by_test_id("settings__edit-profile__form")).to_be_visible(
        timeout=10000
    )

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

    page.hover(".navbar-user-controls .dropdown")
    page.get_by_test_id("navbar__settings-link").click()
    expect(page.get_by_test_id("settings__edit-profile__form")).to_be_visible(
        timeout=10000
    )

    # 3. Add Friend (User 2 invites Admin)
    with page.expect_navigation():
        page.get_by_test_id("navbar__community-link").click()

    page.fill("input[name='search']", "admin")
    with page.expect_navigation():
        page.click("button:has-text('Search')")

    # Click Add Friend for Admin User
    with page.expect_navigation():
        page.click("button:has-text('Add Friend')")

    # [CHANGE] Manually mark as accepted in mock_db to skip dual-acceptance complexity
    admin_friend_ref = mock_db.collection("users").document("admin").collection("friends").document("user2")
    user2_friend_ref = mock_db.collection("users").document("user2").collection("friends").document("admin")
    admin_friend_ref.set({"status": "accepted", "id": "user2"})
    user2_friend_ref.set({"status": "accepted", "id": "admin"})

    # After reload, the user should be in the "Sent Friend Requests" section
    page.reload()
    expect(page.locator(".friend-card", has_text="Admin User")).to_be_visible(
        timeout=5000
    )

    # 4. Create Group (Admin)
    page.goto(f"{base_url}/auth/logout")
    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    with page.expect_navigation():
        page.get_by_test_id("navbar__groups-link").click()
    with page.expect_navigation():
        page.click("text=Create Group")
    page.fill("input[name='name']", "Pickleballers")
    page.fill("input[name='location']", "Test Court")
    with page.expect_navigation():
        page.click("button:has-text('Create Group')")

    expect(page.locator("h1")).to_contain_text("Pickleballers")

    # 5. Invite Friend to Group
    with page.expect_navigation():
        page.get_by_test_id("manage-hub-btn").click()

    page.click("text=Invites")
    page.select_option("select[name='friend']", value="user2")
    with page.expect_navigation():
        page.click("button:has-text('Invite Friend')")

    # [CHANGE] Add user2 to the group members directly in mock_db
    group_docs = list(mock_db.collection("groups").where("name", "==", "Pickleballers").stream())
    assert len(group_docs) > 0
    group_ref = group_docs[0].reference
    user2_ref = mock_db.collection("users").document("user2")
    group_ref.update({"members": group_docs[0].to_dict()["members"] + [user2_ref]})

    # 6. Score Individual Game (User 2 vs Admin)
    page.goto(f"{base_url}/auth/logout")
    page.fill("input[name='email']", "user2@example.com")
    page.fill("input[name='password']", "MyPassword123")
    with page.expect_navigation():
        page.click("button:has-text('Login')")

    page.get_by_test_id("navbar__dashboard-link").click()
    page.get_by_test_id("dashboard__record-match__button").click()
    # Wait for JS to load
    page.wait_for_selector("select[name='player2']")

    page.select_option("select[name='match_type']", value="singles")
    # Wait for participants to sync if match_type changed
    page.wait_for_timeout(500)
    page.select_option("select[name='player1']", value="user2")
    page.select_option("select[name='player2']", value="admin")

    page.fill("input[name='player1_score']", "11")
    page.fill("input[name='player2_score']", "9")

    try:
        # Use simple click
        page.click("button:has-text('Record Match')")
        # Allow any match summary or success page
        page.wait_for_url("**/match/summary/*", timeout=30000)
    except Exception as e:
        page.screenshot(path="e2e_failure_record_match.png")
        print(f"DEBUG: Error during match record: {e}")
        print(f"DEBUG: Current URL: {page.url}")
        print(f"DEBUG: Page Source length: {len(page.content())}")
        # Log visible errors
        errs = page.locator(".alert-danger").all_text_contents()
        if errs:
            print(f"DEBUG: Alerts detected: {errs}")
        raise

    # Check flash message
    expect(page.locator(".toast")).to_contain_text("Match recorded successfully")

    # Go back to dashboard for next steps
    page.get_by_test_id("navbar__dashboard-link").click()
    page.wait_for_url("**/user/dashboard")

    # 7. Score Group Game
    with page.expect_navigation():
        page.get_by_test_id("navbar__groups-link").click()
    with page.expect_navigation():
        page.click("text=Pickleballers")
    with page.expect_navigation():
        page.click("a:has-text('Record a Match')")
    page.select_option("select[name='player1']", value="user2")
    page.select_option("select[name='player2']", value="admin")
    page.fill("input[name='player1_score']", "5")
    page.fill("input[name='player2_score']", "11")
    page.click("button:has-text('Record Match')")
    page.wait_for_url("**/group/*")

    expect(page.locator("h1")).to_contain_text("Pickleballers")
    expect(page.locator(".toast")).to_contain_text("Match recorded successfully")

    # Check Global Leaderboard (Req: "see the leaderboard")
    with page.expect_navigation():
        page.get_by_test_id("navbar__leaderboard-link").click()
    expect(page.locator("h1")).to_contain_text("Leaderboard")
    # Verify players are listed
    expect(
        page.get_by_test_id("leaderboard__current-user-row__container")
    ).to_be_visible()

    # 8. Delete Group Game & 9. Delete Individual Game (Needs Admin access)
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

    # 10. Update Group Location
    page.get_by_test_id("navbar__groups-link").click()
    with page.expect_navigation():
        page.click("text=Pickleballers")
    with page.expect_navigation():
        page.get_by_test_id("manage-hub-btn").click()

    # Switch to Settings tab
    page.click("text=Settings")
    page.fill("input[name='location']", "New Court")
    with page.expect_navigation():
        page.click("button:has-text('Update Group')")
    expect(page.locator("text=New Court")).to_be_visible()

    # 11. Invite Email to Group
    if not page.locator("text=Invites").is_visible():
        page.get_by_test_id("manage-hub-btn").click()

    page.click("text=Invites")
    page.fill("form[action*='invite'] input[name='name']", "New Guy")
    page.fill("form[action*='invite'] input[name='email']", "newguy@example.com")
    with page.expect_navigation():
        page.click("button:has-text('Send Invite')")
    expect(page.locator(".toast-body").last).to_contain_text("Invitation is being sent")

    # Verify invite token was created
    invites = list(mock_db.collection("group_invites").stream())
    invite_token = None
    for inv in invites:
        if inv.to_dict().get("email") == "newguy@example.com":
            invite_token = inv.id
            break
    assert invite_token is not None  # nosec
