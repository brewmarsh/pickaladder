from playwright.sync_api import sync_playwright


def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:27272/auth/login")
    page.screenshot(path="jules-scratch/verification/01_login_page.png")

    # The client-side login is not implemented, so we can't actually log in.
    # We will just navigate to the dashboard to ensure it loads.
    # In a real test, we would need to mock the Firebase client-side SDK.
    page.goto("http://localhost:27272/user/dashboard")
    page.screenshot(path="jules-scratch/verification/02_dashboard.png")

    browser.close()


with sync_playwright() as playwright:
    run(playwright)
