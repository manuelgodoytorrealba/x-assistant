from app.db import get_connection


def ensure_column(cursor, table_name: str, column_name: str, column_def: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        )
        print(f"🛠 Añadida columna {table_name}.{column_name}")


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author TEXT NOT NULL,
        handle TEXT NOT NULL,
        text TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        minutes_since_posted INTEGER NOT NULL,
        likes INTEGER NOT NULL,
        replies INTEGER NOT NULL,
        reposts INTEGER NOT NULL,
        topic_hint TEXT NOT NULL,
        author_priority INTEGER NOT NULL,

        topic_relevance REAL,
        early_engagement REAL,
        reply_potential REAL,
        score REAL,
        recommended_action TEXT,
        priority TEXT,
        fetch_mode TEXT NOT NULL DEFAULT 'reply',

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        reply_1 TEXT,
        reply_2 TEXT,
        quote TEXT,
        new_post TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (post_id) REFERENCES posts (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id INTEGER NOT NULL,
        draft_type TEXT NOT NULL,
        action TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (draft_id) REFERENCES drafts (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts_to_watch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        handle TEXT NOT NULL UNIQUE,
        topic_hint TEXT NOT NULL,
        author_priority INTEGER NOT NULL DEFAULT 5,
        is_active INTEGER NOT NULL DEFAULT 1,
        usage_mode TEXT NOT NULL DEFAULT 'reply',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    ensure_column(cursor, "posts", "fetch_mode", "TEXT NOT NULL DEFAULT 'reply'")
    ensure_column(
        cursor, "accounts_to_watch", "usage_mode", "TEXT NOT NULL DEFAULT 'reply'"
    )

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada.")


if __name__ == "__main__":
    main()
