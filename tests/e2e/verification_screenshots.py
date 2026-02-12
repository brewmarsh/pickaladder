
import pytest
from playwright.sync_api import Page, expect
import os
import re

def test_take_screenshots(app_server, page_with_firebase, mock_db):
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
    page.fill("input[name='name']", "Polish Test Group")
    page.fill("input[name='location']", "UI Review Court")
    page.click("button:has-text('Create Group')")
    page.wait_for_url(re.compile(r".*/group/.*"))

    group_url = page.url

    # Take Screenshot of Group Page
    os.makedirs("/home/jules/verification", exist_ok=True)
    page.screenshot(path="/home/jules/verification/group_page_initial.png", full_page=True)

    # Share Modal
    page.click("button:has-text('Share Group')")
    page.wait_for_selector("#shareGroupModal.show", timeout=5000)
    page.screenshot(path="/home/jules/verification/share_modal_polish.png")
    page.keyboard.press("Escape")
    page.wait_for_selector("#shareGroupModal.show", state="hidden")

    # Trend Chart
    page.click("text=View Leaderboard Trend Chart")
    page.wait_for_selector("canvas#leaderboardChart")
    page.screenshot(path="/home/jules/verification/trend_chart_polish.png")
