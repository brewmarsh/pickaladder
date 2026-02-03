from playwright.sync_api import sync_playwright

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8000/verification/rendered_group.html")

        # Click Teams tab
        page.get_by_role("button", name="Teams").click()

        # Take screenshot
        page.set_viewport_size({"width": 1280, "height": 1000})
        page.screenshot(path="/app/verification/verification_teams.png")

        browser.close()

if __name__ == "__main__":
    verify()
