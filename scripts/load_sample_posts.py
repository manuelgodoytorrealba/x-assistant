from app.db import get_connection
from app.config import RAW_DIR
from app.utils import load_json


def main():
    posts = load_json(RAW_DIR / "sample_posts.json")

    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0

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
                post["author"],
                post["handle"],
                post["text"],
                post["url"],
                post["minutes_since_posted"],
                post["likes"],
                post["replies"],
                post["reposts"],
                post["topic_hint"],
                post["author_priority"],
            ),
        )

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()

    print(f"✅ Posts cargados. Insertados: {inserted}")


if __name__ == "__main__":
    main()
