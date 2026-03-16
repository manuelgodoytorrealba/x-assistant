import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.db import get_connection

X_BASE = "https://x.com"

REPLY_MAX_POST_AGE_MINUTES = 10080  # 7 días
INSPIRATION_MAX_POST_AGE_MINUTES = None

MAX_SCROLL_STEPS = 16
SCROLL_PIXELS = 120

AUTH_FILE = Path("playwright/.auth/x_state.json")


def get_mode_config(mode: str) -> dict:
    if mode == "reply":
        return {
            "allowed_usage_modes": ("reply", "both"),
            "max_post_age_minutes": REPLY_MAX_POST_AGE_MINUTES,
        }
    if mode == "inspiration":
        return {
            "allowed_usage_modes": ("inspiration", "both"),
            "max_post_age_minutes": INSPIRATION_MAX_POST_AGE_MINUTES,
        }
    if mode == "all":
        return {
            "allowed_usage_modes": None,
            "max_post_age_minutes": REPLY_MAX_POST_AGE_MINUTES,
        }
    raise ValueError(f"Modo inválido: {mode}")


def load_accounts(cursor, mode: str = "all"):
    config = get_mode_config(mode)

    query = """
        SELECT handle, topic_hint, author_priority, usage_mode
        FROM accounts_to_watch
        WHERE is_active = 1
    """
    params = []

    allowed_usage_modes = config["allowed_usage_modes"]

    if allowed_usage_modes is not None:
        placeholders = ", ".join(["?"] * len(allowed_usage_modes))
        query += f" AND usage_mode IN ({placeholders})"
        params.extend(allowed_usage_modes)

    query += " ORDER BY topic_hint ASC, author_priority DESC, handle ASC"

    cursor.execute(query, params)
    return cursor.fetchall()


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


def collect_visible_candidates(
    page,
    handle: str,
    seen_urls: set,
    max_post_age_minutes: int | None,
    debug: bool = True,
):
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

            if (
                max_post_age_minutes is not None
                and minutes_since_posted > max_post_age_minutes
            ):
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


def collect_posts_for_handle(
    page,
    handle: str,
    limit: int = 5,
    max_post_age_minutes: int | None = REPLY_MAX_POST_AGE_MINUTES,
):
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
            max_post_age_minutes=max_post_age_minutes,
            debug=(step <= 1),
        )
        candidates.extend(step_candidates)

        if len(candidates) >= limit:
            break

    candidates.sort(key=lambda post: post["minutes_since_posted"])
    return candidates[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["all", "reply", "inspiration"],
        default="all",
        help="Modo de selección de cuentas",
    )
    args = parser.parse_args()

    mode = args.mode
    config = get_mode_config(mode)
    max_post_age_minutes = config["max_post_age_minutes"]

    conn = get_connection()
    cursor = conn.cursor()

    accounts = load_accounts(cursor, mode=mode)

    if not accounts:
        conn.close()
        print("No hay cuentas activas para este modo en accounts_to_watch.")
        return

    print(f"🧭 Modo de fetch: {mode}")
    print(f"📚 Cuentas cargadas: {len(accounts)}")
    if max_post_age_minutes is None:
        print("🕰️ Límite de antigüedad: sin límite")
    else:
        print(f"🕰️ Límite de antigüedad: {max_post_age_minutes} minutos")

    inserted = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

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
            usage_mode = row["usage_mode"]

            print(f"▶ Leyendo @{handle} [{topic_hint} | {usage_mode}] ...")

            try:
                posts = collect_posts_for_handle(
                    page,
                    handle,
                    limit=5,
                    max_post_age_minutes=max_post_age_minutes,
                )
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
                        topic_hint, author_priority, fetch_mode
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        mode,
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
