
import re
from playwright.sync_api import Page, expect

def test_users_page(page: Page):
    print("Starting users page verification...")
    # 1. Arrange: Go to the login page.
    page.goto("http://localhost:27272/auth/login", timeout=60000)

    # Log in
    page.get_by_label("Email").fill("testuser@test.com")
    page.get_by_label("Password").fill("password")
    page.get_by_role("button", name="Login").click()

    # 2. Act: Navigate to the users page
    page.goto("http://localhost:27272/user/users", timeout=60000)

    # 3. Assert: Check that the "Find Players" heading is visible
    expect(page.get_by_role("heading", name="Find Players")).to_be_visible()

    # 4. Screenshot: Capture the final result for visual verification.
    page.screenshot(path="jules-scratch/verification/users-page.png")
    print("Screenshot taken.")

print("Running Playwright script...")
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    test_users_page(page)
    browser.close()
print("Playwright script finished.")
