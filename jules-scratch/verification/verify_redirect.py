from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # The application is running on port 27272.
    page.goto("http://localhost:27272")

    # The new index.html should redirect to the login page.
    expect(page).to_have_url("http://localhost:27272/login")

    # Check that the page title is correct.
    expect(page).to_have_title("pickaladder - Login")

    # Verify that the CSS is loaded by checking the color of the h1 element.
    h1 = page.locator("h1")
    expect(h1).to_have_css("color", "rgb(51, 51, 51)")

    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)