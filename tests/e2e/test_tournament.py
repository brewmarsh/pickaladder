"""End-to-end tests for tournament features."""

from __future__ import annotations

import os
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
        page.click("text=Tournaments")
    with page.expect_navigation():
        page.click("text=Create Tournament")
    page.fill("input[name='name']", "Winter Open")
    page.fill("input[name='date']", "2026-12-01")
    page.fill("input[name='location']", "Central Park")
    page.select_option("select[name='match_type']", value="singles")
    with page.expect_navigation():
        page.click("button:has-text('Create Tournament')")

    expect(page.locator("h2")).to_contain_text("Winter Open")
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
    # Create the directory safely in the current workspace
    verify_dir = "verification"
    os.makedirs(verify_dir, exist_ok=True)

    # Save with a relative path
    page.screenshot(path=os.path.join(verify_dir, "tournament_invite.png"))
    expect(page.locator("select[name='user_id']")).to_contain_text("friend_user")

    # 3. Check Directions button
    directions_btn = page.locator("text=Directions")
    expect(directions_btn).to_be_visible()
    expect(directions_btn).to_have_attribute(
        "href", "https://www.google.com/maps/search/?api=1&query=Central%20Park"
    )

    # 4. Complete Tournament (as owner)
    with page.expect_navigation():
        page.click("text=Complete Tournament")

    expect(page.locator(".badge-success", has_text="Completed")).to_be_visible()
    # Podium is only shown if there are matches, but we verified the flow works.
