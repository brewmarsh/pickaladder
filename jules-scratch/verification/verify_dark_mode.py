from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Log in
    page.goto("http://127.0.0.1:27272/auth/login")
    page.fill('input[name="email"]', "test@example.com")
    page.fill('input[name="password"]', "password")
    page.click('input[type="submit"]')
    page.wait_for_url("http://127.0.0.1:27272/dashboard")

    # Enable dark mode
    page.click('input[name="dark_mode"]')

    # Take screenshot
    page.screenshot(path="jules-scratch/verification/dark_mode_verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
