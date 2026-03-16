import argparse

from app.db import get_connection

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

BLUE = "\033[94m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"


def color(text, tone):
    return f"{tone}{text}{RESET}"


def format_post_age(minutes_since_posted):
    if minutes_since_posted is None:
        return "desconocida"

    try:
        minutes = int(minutes_since_posted)
    except (TypeError, ValueError):
        return "desconocida"

    if minutes < 60:
        return f"{minutes} min"

    if minutes < 1440:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} h"
        return f"{hours} h {remaining_minutes} min"

    days = minutes // 1440
    remaining_hours = (minutes % 1440) // 60
    if remaining_hours == 0:
        return f"{days} d"
    return f"{days} d {remaining_hours} h"


def get_digest_config(mode: str) -> dict:
    if mode == "inspiration":
        return {
            "title": "=== X INSPIRATION DIGEST ===",
            "field_1_label": "observation",
            "field_2_label": "angle",
            "field_3_label": "quote_frame",
            "field_4_label": "post_seed",
        }

    return {
        "title": "=== DAILY X DIGEST ===",
        "field_1_label": "reply_1",
        "field_2_label": "reply_2",
        "field_3_label": "quote",
        "field_4_label": "new_post",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reply", "inspiration"],
        default="reply",
    )
    args = parser.parse_args()
    mode = args.mode

    config = get_digest_config(mode)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            d.id AS draft_id,
            p.handle,
            p.author,
            p.topic_hint,
            p.score,
            p.priority,
            p.recommended_action,
            p.text,
            p.url,
            p.minutes_since_posted,
            p.created_at,
            p.fetch_mode,
            d.reply_1,
            d.reply_2,
            d.quote,
            d.new_post
        FROM drafts d
        JOIN posts p ON d.post_id = p.id
        WHERE p.fetch_mode = ?
        ORDER BY p.score DESC
        """,
        (mode,),
    )

    rows = cursor.fetchall()
    conn.close()

    print("\n" + color(config["title"], BOLD + WHITE) + "\n")
    print(color(f"modo: {mode}", DIM + WHITE) + "\n")

    if not rows:
        print(color("No hay drafts generados para este modo.", GRAY))
        return

    for i, row in enumerate(rows, start=1):
        age = format_post_age(row["minutes_since_posted"])
        handle = (row["handle"] or "").lstrip("@")

        header = (
            f"[{i}] draft_id: {row['draft_id']} | @{handle} | "
            f"score: {row['score']} | prioridad: {row['priority']}"
        )
        meta = f"tema: {row['topic_hint']} | acción: {row['recommended_action']}"
        age_line = f"edad: {age}"
        url_line = f"url: {row['url'] or 'sin url'}"

        print(color(header, BOLD + WHITE))
        print(color(meta, DIM + WHITE))
        print(color(age_line, DIM + WHITE))
        print(color(url_line, DIM + WHITE))

        print()
        print(color("POST ORIGINAL", BOLD + BLUE))
        print(color(row["text"], BLUE))

        print()
        print(color(config["field_1_label"], BOLD + GREEN))
        print(color(row["reply_1"] or "", GREEN))

        print()
        print(color(config["field_2_label"], BOLD + CYAN))
        print(color(row["reply_2"] or "", CYAN))

        print()
        print(color(config["field_3_label"], BOLD + YELLOW))
        print(color(row["quote"] or "", YELLOW))

        print()
        print(color(config["field_4_label"], BOLD + MAGENTA))
        print(color(row["new_post"] or "", MAGENTA))

        print("\n" + color("-" * 90, GRAY) + "\n")


if __name__ == "__main__":
    main()
