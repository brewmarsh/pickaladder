from playwright.sync_api import sync_playwright
import os

def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})

        # Screenshot Admin Page
        abs_path = os.path.abspath('admin_rendered.html')
        page.goto(f'file://{abs_path}')
        # Add some CSS to make it look decent since it won't load external CSS properly from file://
        # unless we are careful. But pickaladder uses local static files.
        # Let's hope it finds them or we just check the structure.
        page.screenshot(path='admin_verification.png', full_page=True)

        # Screenshot Footer
        abs_path_footer = os.path.abspath('footer_rendered.html')
        page.goto(f'file://{abs_path_footer}')
        page.screenshot(path='footer_verification.png')

        browser.close()

if __name__ == "__main__":
    take_screenshots()
