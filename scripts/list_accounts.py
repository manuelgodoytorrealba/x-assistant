from app.db import get_connection


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, handle, topic_hint, author_priority, is_active, created_at
    FROM accounts_to_watch
    ORDER BY author_priority DESC, handle ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n=== ACCOUNTS TO WATCH ===\n")

    if not rows:
        print("No hay cuentas todavía.\n")
        return

    for row in rows:
        status = "active" if row["is_active"] == 1 else "inactive"
        print(
            f"id={row['id']} | @{row['handle']} | topic={row['topic_hint']} | "
            f"priority={row['author_priority']} | {status}"
        )


if __name__ == "__main__":
    main()
