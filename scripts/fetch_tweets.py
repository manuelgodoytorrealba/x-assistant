import re
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from app.db import get_connection

X_BASE = "https://x.com"


def parse_minutes_since(iso_date: str) -> int:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        return max(1, int(diff.total_seconds() // 60))
    except Exception:
        return 60


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
    """
    Intenta leer métricas desde aria-label del botón correspondiente.
    Ejemplos típicos:
    - "5 Replies. Reply"
    - "12 Likes. Like"
    - "3 Reposts. Repost"
    """
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

    articles = page.locator("article[data-testid='tweet']")
    total = articles.count()
    count = min(total, limit)

    print(f"   → tweets detectados en @{handle}: {total}")

    results = []

    for i in range(count):
        article = articles.nth(i)

        try:
            text = extract_tweet_text(article)
            if not text:
                print(f"   ⚠️ tweet {i+1}: sin texto, se omite")
                continue

            iso_date = extract_iso_date(article)
            minutes_since_posted = parse_minutes_since(iso_date)
            tweet_url = extract_tweet_url(article)

            if not tweet_url:
                print(f"   ⚠️ tweet {i+1}: sin URL, se omite")
                continue

            replies = extract_metric_from_aria(article, "reply")
            reposts = extract_metric_from_aria(article, "retweet")
            likes = extract_metric_from_aria(article, "like")

            results.append(
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

        except Exception as e:
            print(f"   ⚠️ error procesando tweet {i+1} de @{handle}: {e}")
            continue

    return results


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT handle, topic_hint, author_priority
    FROM accounts_to_watch
    WHERE is_active = 1
    ORDER BY author_priority DESC
    """)

    accounts = cursor.fetchall()

    if not accounts:
        conn.close()
        print("No hay cuentas activas en accounts_to_watch.")
        return

    inserted = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(5000)

        for row in accounts:
            handle = row["handle"]
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

            page.wait_for_timeout(1500)

        browser.close()

    conn.commit()
    conn.close()

    print(f"✅ Fetch terminado. Nuevos posts insertados: {inserted}")


if __name__ == "__main__":
    main()
