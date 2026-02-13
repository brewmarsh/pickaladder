
import pytest
from playwright.sync_api import Page, expect
import os
import re

def test_verify_fixes(app_server, page_with_firebase, mock_db):
    page = page_with_firebase
    base_url = app_server

    # Setup Admin
    page.goto(f"{base_url}/auth/login")
    if "/auth/install" in page.url:
        page.fill("input[name='username']", "admin")
        page.fill("input[name='email']", "admin@example.com")
        page.fill("input[name='password']", "password")
        page.fill("input[name='name']", "Admin User")
        page.click("button:has-text('Create Admin')")
        page.wait_for_url("**/auth/login")

    # Login as Admin
    page.fill("input[name='email']", "admin@example.com")
    page.fill("input[name='password']", "password")
    page.click("button:has-text('Login')")
    page.wait_for_url("**/user/dashboard")

    # Create Group
    page.goto(f"{base_url}/group/create")
    page.fill("input[name='name']", "Fixes Verification Group")
    page.fill("input[name='location']", "Court 1")
    page.click("button:has-text('Create Group')")
    page.wait_for_url(re.compile(r".*/group/.*"))

    # Check if Gear icon is visible (means g.user['uid'] matched group owner)
    gear_icon = page.locator(".btn-edit-gear")
    expect(gear_icon).to_be_visible()

    # Check Share Modal for pluralization
    page.click("button:has-text('Share')")
    page.wait_for_selector("#shareGroupModal.show", timeout=5000)

    stat_text = page.locator(".social-share-card-stat").text_content()
    print(f"Stat text: {stat_text}")
    # Since it's a new group, rank is Member or something.
    # In group.html:
    # {% set ns = namespace(user_rank='Member', streak=0) %}
    # If no leaderboard entry found for user.
    # But wait, the user IS in the leaderboard because they are a member.

    os.makedirs("/home/jules/verification", exist_ok=True)
    page.screenshot(path="/home/jules/verification/fixes_verified_modal.png")
