"""End-to-end tests for tournament features."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, expect


def test_tournament_flow(
    app_server: str, page_with_firebase: Page, mock_db: Any
) -> None:
    """Test the complete tournament flow: creation."""
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
    page.fill("input[name='name']", "Winter Open")
    page.fill("input[name='start_date']", "2026-12-01")
    page.fill("input[name='venue_name']", "Central Park")
    page.fill("input[name='address']", "Central Park, New York, NY")
    page.check("input[name='match_type'][value='singles']")
    with page.expect_navigation():
        page.click("button:has-text('Create Tournament')")

    expect(page.locator("h1")).to_contain_text("Winter Open")
    expect(page.locator(".badge-warning", has_text="Active")).to_be_visible()
