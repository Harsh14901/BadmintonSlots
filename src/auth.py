from playwright.sync_api import sync_playwright


BASE_URL = "https://towerhamletscouncil.gladstonego.cloud"


def get_jwt() -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE_URL}/book")
        page.wait_for_load_state("networkidle")

        cookies = context.cookies()
        jwt_cookie = next((c for c in cookies if c["name"] == "Jwt"), None)
        browser.close()

        if not jwt_cookie:
            raise RuntimeError("Failed to obtain JWT cookie")
        return jwt_cookie["value"]
