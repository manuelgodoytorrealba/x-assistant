from pathlib import Path

from playwright.sync_api import sync_playwright

AUTH_DIR = Path("playwright/.auth")
AUTH_FILE = AUTH_DIR / "x_state.json"


def main():
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://x.com/login", wait_until="domcontentloaded")

        print("\n🔐 Inicia sesión manualmente en X.")
        print("Cuando ya estés dentro de tu cuenta y veas el home/feed, vuelve aquí.")
        input("Pulsa ENTER para guardar la sesión... ")

        context.storage_state(path=str(AUTH_FILE))
        browser.close()

    print(f"✅ Sesión guardada en: {AUTH_FILE}")


if __name__ == "__main__":
    main()
