"""End-to-end tests for tournament features."""

from __future__ import annotations

import re
from typing import Any

from playwright.sync_api import Page, expect


def test_tournament_flow(
    app_server: str, page_with_firebase: Page, mock_db: Any
) -> None:
    """Test the complete tournament flow: creation and completion."""
    page = page_with_firebase
    base_url = app_server
    page.on("dialog", lambda dialog: dialog.accept())

    # 1. Login as Admin
    page.goto(f"{base_url}/auth/login")
    if "/auth/install" in page.url:
        page.fill("input[name='username']", "admin")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        page.fill("input[name='name']", "Admin User")
        with page.expect_navigation():
            page.click("button:has-text('Create Admin')")
        page.wait_for_url("**/auth/login")

    page.wait_for_selector("input[name='email']")
    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    with page.expect_navigation():
        page.click(".btn:has-text('Login')")

    # 2. Create a Tournament
    with page.expect_navigation():
        page.click(".navbar a:has-text('Tournaments')")
    with page.expect_navigation():
        page.click("a.btn-action:has-text('Create Tournament')")

    page.wait_for_selector("input[name='name']")
    page.fill("input[name='name']", "Winter Open")

    # We standardized to start_date in the form
    page.fill("input[name='start_date']", "2026-12-01")
    page.fill("input[name='address']", "Central Park")

    # Click radio button by label
    page.click("label:has-text('Singles')")

    with page.expect_navigation():
        page.click("button:has-text('Create Tournament')")

    # The title should be in the hero card
    expect(page.locator("h1").first).to_contain_text("Winter Open")
    expect(page.locator(".badge-warning", has_text="Active")).to_be_visible()

    # Create a friend to verify the Invite dropdown
    friend_id = "friend_user"
    mock_db.collection("users").document(friend_id).set(
        {
            "username": "friend_user",
            "email": "friend@example.com",
            "name": "Friend User",
            "createdAt": "2023-01-01T00:00:00",
        }
    )
    mock_db.collection("users").document("admin").collection("friends").document(
        friend_id
    ).set({"status": "accepted"})

    page.reload()
    expect(page.locator("select[name='user_id']")).to_contain_text("friend_user")

    # 3. Check Directions button
    directions_btn = page.locator("text=Directions")
    expect(directions_btn).to_be_visible()
    expect(directions_btn).to_have_attribute(
        "href", re.compile(".*Central%20Park")
    )

    # 4. Record a Match (Verify Summary Redirect)
    # First, ensure friend_user is a participant for the match recording to work easily
    tournament_id = page.url.split("/")[-1]
    mock_db.collection("tournaments").document(tournament_id).update(
        {"participant_ids": ["admin", "friend_user"]}
    )
    page.reload()

    # Click the Bracket tab to see the Record Match button
    page.click("button:has-text('Bracket')")
    expect(page.locator("#bracket")).to_be_visible()

    with page.expect_navigation():
        page.click("#bracket a:has-text('Record Match')")

    page.select_option("select[name='player1']", value="admin")
    page.select_option("select[name='player2']", value="friend_user")
    page.fill("input[name='player1_score']", "11")
    page.fill("input[name='player2_score']", "5")

    with page.expect_navigation():
        page.click("button:has-text('Record Match')")

    # Verify redirection back to tournament view
    expect(page).to_have_url(re.compile(f".*/tournaments/{tournament_id}"))

    # 5. Complete Tournament (as owner)
    with page.expect_navigation():
        page.click("text=Complete Tournament")

    expect(page.locator(".badge-success", has_text="Completed")).to_be_visible()
