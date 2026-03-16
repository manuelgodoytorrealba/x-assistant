from app.db import get_connection


def main():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM drafts")
    cursor.execute("DELETE FROM posts")
    cursor.execute("DELETE FROM feedback")

    conn.commit()
    conn.close()

    print("✅ Runtime data limpiada: posts, drafts, feedback.")


if __name__ == "__main__":
    main()
