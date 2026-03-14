from app.db import get_connection
from app.models import ScoredPost
from app.generators import generate_drafts, should_generate_for_post


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM drafts")

    cursor.execute("""
    SELECT id, author, handle, text, url,
           minutes_since_posted, likes, replies, reposts,
           topic_hint, author_priority,
           topic_relevance, early_engagement, reply_potential,
           score, recommended_action, priority
    FROM posts
    WHERE score IS NOT NULL
      AND score >= 78
    ORDER BY score DESC
    """)

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

        if should_generate_for_post(post):
            selected_rows.append((row, post))
        else:
            print(f"⏭ Omitido @{post.handle}: poco material editorial")

    for index, (row, post) in enumerate(selected_rows, start=1):
        handle = (row["handle"] or "").lstrip("@")
        print(f"▶ Generando drafts para @{handle} ({index}/{len(selected_rows)})")

        drafts = generate_drafts(post)

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

    print("✅ Borradores generados en SQLite.")


if __name__ == "__main__":
    main()
