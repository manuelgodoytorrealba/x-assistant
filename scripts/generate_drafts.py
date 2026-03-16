import argparse

from app.db import get_connection
from app.models import ScoredPost
from app.generators import generate_drafts, get_skip_reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reply", "inspiration"],
        default="reply",
    )
    args = parser.parse_args()
    mode = args.mode

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM drafts")

    if mode == "reply":
        cursor.execute(
            """
            SELECT id, author, handle, text, url,
                   minutes_since_posted, likes, replies, reposts,
                   topic_hint, author_priority,
                   topic_relevance, early_engagement, reply_potential,
                   score, recommended_action, priority
            FROM posts
            WHERE fetch_mode = ?
              AND score IS NOT NULL
              AND score >= 65
              AND recommended_action IN ('reply', 'quote', 'consider')
            ORDER BY score DESC
            """,
            (mode,),
        )
    else:
        cursor.execute(
            """
            SELECT id, author, handle, text, url,
                   minutes_since_posted, likes, replies, reposts,
                   topic_hint, author_priority,
                   topic_relevance, early_engagement, reply_potential,
                   score, recommended_action, priority
            FROM posts
            WHERE fetch_mode = ?
              AND score IS NOT NULL
              AND score >= 55
              AND recommended_action IN ('capture', 'consider')
            ORDER BY score DESC
            """,
            (mode,),
        )

    rows = cursor.fetchall()
    selected_rows = []

    for row in rows:
        post = ScoredPost(
            author=row["author"],
            handle=row["handle"],
            text=row["text"],
            url=row["url"],
            minutes_since_posted=row["minutes_since_posted"],
            likes=row["likes"],
            replies=row["replies"],
            reposts=row["reposts"],
            topic_hint=row["topic_hint"],
            author_priority=row["author_priority"],
            topic_relevance=row["topic_relevance"],
            early_engagement=row["early_engagement"],
            reply_potential=row["reply_potential"],
            score=row["score"],
            recommended_action=row["recommended_action"],
            priority=row["priority"],
        )

        handle = (row["handle"] or "").lstrip("@")
        reason = get_skip_reason(post, mode=mode)

        if reason is None:
            selected_rows.append((row, post))
        else:
            print(f"⏭ Omitido @{handle}: {reason}")

    if not selected_rows:
        conn.commit()
        conn.close()
        print(f"⚠️ No hay posts seleccionados para generar drafts en modo {mode}.")
        return

    for index, (row, post) in enumerate(selected_rows, start=1):
        handle = (row["handle"] or "").lstrip("@")
        print(
            f"▶ Generando drafts para @{handle} ({index}/{len(selected_rows)}) [{mode}]"
        )

        drafts = generate_drafts(post, mode=mode)

        cursor.execute(
            """
            INSERT INTO drafts (
                post_id, reply_1, reply_2, quote, new_post
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                drafts["reply_1"],
                drafts["reply_2"],
                drafts["quote"],
                drafts["new_post"],
            ),
        )

    conn.commit()
    conn.close()

    print(f"✅ Borradores generados en SQLite para modo {mode}.")


if __name__ == "__main__":
    main()
