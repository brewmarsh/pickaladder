from playwright.sync_api import Page, expect


def test_rivalry_ui(page: Page):
    page.goto("http://localhost:5000")
    page.get_by_role("link", name="Login").click()
    page.get_by_label("Email").fill("testuser@test.com")
    page.get_by_label("Password").fill("password")
    page.get_by_role("button", name="Log In").click()
    page.get_by_role("link", name="View Groups").click()
    page.get_by_role("link", name="Test Group").click()

    player1_select = page.locator("select#player1-select")
    player2_select = page.locator("select#player2-select")

    player1_select.select_option(label="Test User")
    player2_select.select_option(label="Another User")

    expect(page.locator(".tale-of-the-tape")).to_be_visible()
    expect(page.get_by_text("Tale of the Tape")).to_be_visible()
    expect(page.get_by_text("Avg Points Scored")).to_be_visible()
    expect(page.get_by_text("Partnership Record")).to_be_visible()

    page.screenshot(path="tests/e2e/screenshots/rivalry_ui.png")
