from app.db import get_connection


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
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
        d.reply_1,
        d.reply_2,
        d.quote,
        d.new_post
    FROM drafts d
    JOIN posts p ON d.post_id = p.id
    ORDER BY p.score DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n=== DAILY X DIGEST ===\n")

    for i, row in enumerate(rows, start=1):
        print(
            f"[{i}] draft_id: {row['draft_id']} | {row['handle']} | score: {row['score']} | prioridad: {row['priority']}"
        )
        print(f"tema: {row['topic_hint']} | acción: {row['recommended_action']}")
        print(f"post: {row['text']}")
        print("\n  reply_1:")
        print(f"  {row['reply_1']}")
        print("\n  reply_2:")
        print(f"  {row['reply_2']}")
        print("\n  quote:")
        print(f"  {row['quote']}")
        print("\n  new_post:")
        print(f"  {row['new_post']}")
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()
