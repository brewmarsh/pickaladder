import os
import time
from playwright.sync_api import sync_playwright

def verify_leaderboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 1000})
        page = context.new_page()

        # We need to bypass login if possible or just login as admin
        # Since MOCK_DB is true, we might need to setup the user

        base_url = "http://localhost:27272"

        try:
            # First, navigate to login to see if it's up
            page.goto(f"{base_url}/auth/login")
            time.sleep(2)

            # Since it's MOCK_DB, we might need to "install" if it's the first run
            if "/auth/install" in page.url:
                page.fill("input[name='username']", "admin")
                page.fill("input[name='email']", "admin@example.com")
                page.fill("input[name='password']", "password")
                page.fill("input[name='name']", "Admin User")
                page.click("button[type='submit']")
                time.sleep(2)

            # Login
            page.goto(f"{base_url}/auth/login")
            page.fill("input[name='email']", "admin@example.com")
            page.fill("input[name='password']", "password")
            page.click("button[type='submit']")
            time.sleep(2)

            # Navigate to Leaderboard
            page.goto(f"{base_url}/match/leaderboard")
            time.sleep(2)

            # Take screenshot
            page.screenshot(path="verification/leaderboard_hub.png", full_page=True)
            print("Screenshot saved to verification/leaderboard_hub.png")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    verify_leaderboard()
