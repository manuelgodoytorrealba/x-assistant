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


def main():
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
            d.reply_1,
            d.reply_2,
            d.quote,
            d.new_post
        FROM drafts d
        JOIN posts p ON d.post_id = p.id
        ORDER BY p.score DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    print("\n" + color("=== DAILY X DIGEST ===", BOLD + WHITE) + "\n")

    if not rows:
        print(color("No hay drafts generados.", GRAY))
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
        print(color("reply_1", BOLD + GREEN))
        print(color(row["reply_1"], GREEN))

        print()
        print(color("reply_2", BOLD + CYAN))
        print(color(row["reply_2"], CYAN))

        print()
        print(color("quote", BOLD + YELLOW))
        print(color(row["quote"], YELLOW))

        print()
        print(color("new_post", BOLD + MAGENTA))
        print(color(row["new_post"], MAGENTA))

        print("\n" + color("-" * 90, GRAY) + "\n")


if __name__ == "__main__":
    main()
