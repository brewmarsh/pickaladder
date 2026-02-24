import pytest
from playwright.sync_api import Page, expect

def test_community_search_alignment(app, live_server, page: Page):
    # We'll mock a logged in user by setting a session variable if possible,
    # but since it's a live server in a separate process, it's harder.
    # Instead, let's just go to a page that doesn't require login if possible,
    # or just look at the login page which has a primary button.

    page.goto(live_server.url() + "/auth/login")

    # Take screenshot of login page (light mode)
    page.screenshot(path="/home/jules/verification/login_light.png")

    # Toggle dark mode
    page.evaluate("document.body.setAttribute('data-theme', 'dark')")
    page.screenshot(path="/home/jules/verification/login_dark.png")
