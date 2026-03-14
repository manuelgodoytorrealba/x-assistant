from app.db import get_connection


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        f.id,
        f.draft_id,
        f.draft_type,
        f.action,
        f.notes,
        f.created_at,
        p.handle,
        p.text
    FROM feedback f
    JOIN drafts d ON f.draft_id = d.id
    JOIN posts p ON d.post_id = p.id
    ORDER BY f.created_at DESC, f.id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    print("\n=== FEEDBACK HISTORY ===\n")

    if not rows:
        print("No hay feedback registrado todavía.\n")
        return

    for row in rows:
        print(
            f"feedback_id: {row['id']} | draft_id: {row['draft_id']} | {row['handle']}"
        )
        print(
            f"tipo: {row['draft_type']} | acción: {row['action']} | fecha: {row['created_at']}"
        )
        if row["notes"]:
            print(f"notas: {row['notes']}")
        print(f"post: {row['text']}")
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()
