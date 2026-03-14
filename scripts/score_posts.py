from app.db import get_connection
from app.models import PostCandidate
from app.scoring import score_post


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, author, handle, text, url,
           minutes_since_posted, likes, replies, reposts,
           topic_hint, author_priority
    FROM posts
    """)

    rows = cursor.fetchall()

    scored_count = 0

    for row in rows:
        post = PostCandidate(
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
        )

        scored = score_post(post)

        cursor.execute(
            """
        UPDATE posts
        SET topic_relevance = ?,
            early_engagement = ?,
            reply_potential = ?,
            score = ?,
            recommended_action = ?,
            priority = ?
        WHERE id = ?
        """,
            (
                scored.topic_relevance,
                scored.early_engagement,
                scored.reply_potential,
                scored.score,
                scored.recommended_action,
                scored.priority,
                row["id"],
            ),
        )

        scored_count += 1

    conn.commit()

    cursor.execute("""
    SELECT handle, score, recommended_action
    FROM posts
    ORDER BY score DESC
    """)

    results = cursor.fetchall()

    conn.close()

    print("✅ Posts puntuados correctamente.")
    for post in results:
        print(f'- {post["handle"]} | {post["score"]} | {post["recommended_action"]}')


if __name__ == "__main__":
    main()
