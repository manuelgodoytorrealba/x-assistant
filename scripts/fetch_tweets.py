import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.db import get_connection

X_BASE = "https://x.com"
MAX_POST_AGE_MINUTES = 10080  # 3 días
MAX_SCROLL_STEPS = 16
SCROLL_PIXELS = 120

AUTH_FILE = Path("playwright/.auth/x_state.json")


def parse_minutes_since(iso_date: str):
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        return max(1, int(diff.total_seconds() // 60))
    except Exception:
        return None


def safe_int(text: str) -> int:
    text = (text or "").strip().upper().replace(",", "")
    if not text:
        return 0

    multiplier = 1
    if text.endswith("K"):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1000000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except Exception:
        return 0


def extract_metric_from_aria(article, testid: str) -> int:
    try:
        button = article.locator(f"[data-testid='{testid}']").first

        if button.count() == 0:
            return 0

        aria = button.get_attribute("aria-label", timeout=1500) or ""
        if not aria:
            return 0

        match = re.search(r"([\d,.]+[KM]?)", aria.upper())
        if not match:
            return 0

        return safe_int(match.group(1))
    except Exception:
        return 0


def extract_tweet_url(article) -> str:
    try:
        time_el = article.locator("time").first
        parent_link = time_el.locator("xpath=..")
        href = parent_link.get_attribute("href", timeout=1500) or ""
        if href.startswith("/"):
            return f"{X_BASE}{href}"
        return href
    except Exception:
        return ""


def extract_tweet_text(article) -> str:
    try:
        locator = article.locator("div[data-testid='tweetText']").first
        return (locator.inner_text(timeout=2000) or "").strip()
    except Exception:
        return ""


def extract_iso_date(article) -> str:
    try:
        time_el = article.locator("time").first
        return time_el.get_attribute("datetime", timeout=1500) or ""
    except Exception:
        return ""


def is_pinned_tweet(article) -> bool:
    try:
        text = article.inner_text(timeout=1500).lower()
        return "pinned" in text or "fijado" in text
    except Exception:
        return False


def is_repost_tweet(article) -> bool:
    try:
        text = article.inner_text(timeout=1500).lower()
        return " reposted" in text or "reposted " in text or " ha reposted " in text
    except Exception:
        return False


def go_to_posts_tab(page):
    possible_selectors = [
        "a[role='tab']:has-text('Posts')",
        "div[role='tab']:has-text('Posts')",
        "a[role='tab']:has-text('Publicaciones')",
        "div[role='tab']:has-text('Publicaciones')",
    ]

    for selector in possible_selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=1500):
                locator.click(timeout=2000)
                page.wait_for_timeout(2000)
                return
        except Exception:
            continue


def accept_cookies_if_present(page):
    possible_selectors = [
        "button:has-text('Accept all cookies')",
        "button:has-text('Aceptar todas las cookies')",
        "button:has-text('Accept')",
        "button:has-text('Aceptar')",
    ]

    for selector in possible_selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                locator.click(timeout=2000)
                page.wait_for_timeout(1500)
                print("   → cookies aceptadas")
                return
        except Exception:
            continue


def focus_timeline(page):
    possible_selectors = [
        "main",
        "[data-testid='primaryColumn']",
        "article[data-testid='tweet']",
    ]

    for selector in possible_selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                locator.hover(timeout=2000)
                page.wait_for_timeout(300)
                return
        except Exception:
            continue


def collect_visible_candidates(page, handle: str, seen_urls: set, debug: bool = True):
    candidates = []

    articles = page.locator("article[data-testid='tweet']")
    total = articles.count()

    if debug:
        print(f"   → tweets detectados en @{handle}: {total}")

    for i in range(total):
        article = articles.nth(i)

        try:
            if is_pinned_tweet(article):
                if debug:
                    print(f"   ⚠️ tweet {i+1}: fijado, se omite")
                continue

            if is_repost_tweet(article):
                if debug:
                    print(f"   ⚠️ tweet {i+1}: repost, se omite")
                continue

            text = extract_tweet_text(article)
            if not text:
                if debug:
                    print(f"   ⚠️ tweet {i+1}: sin texto, se omite")
                continue

            iso_date = extract_iso_date(article)
            if not iso_date:
                if debug:
                    print(f"   ⚠️ tweet {i+1}: sin fecha, se omite")
                continue

            minutes_since_posted = parse_minutes_since(iso_date)
            if minutes_since_posted is None:
                if debug:
                    print(f"   ⚠️ tweet {i+1}: fecha inválida, se omite")
                continue

            tweet_url = extract_tweet_url(article)
            if not tweet_url:
                if debug:
                    print(f"   ⚠️ tweet {i+1}: sin URL, se omite")
                continue

            if tweet_url in seen_urls:
                continue

            if minutes_since_posted > MAX_POST_AGE_MINUTES:
                if debug:
                    print(
                        f"   ⚠️ tweet {i+1}: demasiado viejo "
                        f"({minutes_since_posted} min), se omite"
                    )
                continue

            replies = extract_metric_from_aria(article, "reply")
            reposts = extract_metric_from_aria(article, "retweet")
            likes = extract_metric_from_aria(article, "like")

            preview = text.replace("\n", " ")[:90]
            if debug:
                print(
                    f"   ✅ tweet candidato {i+1}: "
                    f"{minutes_since_posted} min | {preview}"
                )

            candidates.append(
                {
                    "handle": handle,
                    "text": text,
                    "url": tweet_url,
                    "minutes_since_posted": minutes_since_posted,
                    "likes": likes,
                    "replies": replies,
                    "reposts": reposts,
                }
            )
            seen_urls.add(tweet_url)

        except Exception as e:
            if debug:
                print(f"   ⚠️ error procesando tweet {i+1} de @{handle}: {e}")
            continue

    return candidates


def collect_posts_for_handle(page, handle: str, limit: int = 5):
    url = f"{X_BASE}/{handle}"
    print(f"   → abriendo {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    try:
        page.wait_for_selector("article[data-testid='tweet']", timeout=10000)
    except PlaywrightTimeoutError:
        print(f"   ⚠️ No se encontraron tweets visibles para @{handle}")
        return []

    accept_cookies_if_present(page)
    page.wait_for_timeout(1000)

    go_to_posts_tab(page)
    page.wait_for_timeout(1500)

    candidates = []
    seen_urls = set()

    focus_timeline(page)

    for step in range(MAX_SCROLL_STEPS + 1):
        if step == 0:
            print("   → inspeccionando zona superior visible")
        else:
            page.mouse.wheel(0, SCROLL_PIXELS)
            page.wait_for_timeout(900)
            print(f"   → scroll fino {step}/{MAX_SCROLL_STEPS}")

        step_candidates = collect_visible_candidates(
            page=page,
            handle=handle,
            seen_urls=seen_urls,
            debug=(step <= 1),
        )
        candidates.extend(step_candidates)

        if len(candidates) >= limit:
            break

    candidates.sort(key=lambda post: post["minutes_since_posted"])
    return candidates[:limit]


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT handle, topic_hint, author_priority
        FROM accounts_to_watch
        WHERE is_active = 1
        ORDER BY author_priority DESC
        """
    )

    accounts = cursor.fetchall()

    if not accounts:
        conn.close()
        print("No hay cuentas activas en accounts_to_watch.")
        return

    inserted = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        if AUTH_FILE.exists():
            print(f"🔐 Usando sesión guardada: {AUTH_FILE}")
            context = browser.new_context(storage_state=str(AUTH_FILE))
        else:
            print("⚠️ No se encontró sesión guardada. Usando modo público.")
            context = browser.new_context()

        page = context.new_page()
        page.set_default_timeout(5000)

        for row in accounts:
            raw_handle = row["handle"]
            handle = (raw_handle or "").lstrip("@")
            topic_hint = row["topic_hint"]
            author_priority = row["author_priority"]

            print(f"▶ Leyendo @{handle} ...")

            try:
                posts = collect_posts_for_handle(page, handle, limit=5)
            except Exception as e:
                print(f"⚠️ Error leyendo @{handle}: {e}")
                continue

            print(f"   → posts útiles extraídos: {len(posts)}")

            for post in posts:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO posts (
                        author, handle, text, url,
                        minutes_since_posted, likes, replies, reposts,
                        topic_hint, author_priority
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        handle,
                        f"@{handle}",
                        post["text"],
                        post["url"],
                        post["minutes_since_posted"],
                        post["likes"],
                        post["replies"],
                        post["reposts"],
                        topic_hint,
                        author_priority,
                    ),
                )

                if cursor.rowcount > 0:
                    inserted += 1

        context.close()
        browser.close()

    conn.commit()
    conn.close()

    print(f"✅ Fetch terminado. Nuevos posts insertados: {inserted}")


if __name__ == "__main__":
    main()
