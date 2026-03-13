import argparse
from app.db import get_connection


VALID_TOPICS = {"enso", "jano", "1710"}


def main():
    parser = argparse.ArgumentParser(description="Añadir cuenta a vigilar")
    parser.add_argument("--handle", required=True, help="Handle sin @, por ejemplo: paulgraham")
    parser.add_argument("--topic", required=True, help="enso, jano o 1710")
    parser.add_argument("--priority", type=int, default=5, help="Prioridad 1-10")
    args = parser.parse_args()

    handle = args.handle.strip().lstrip("@")
    topic = args.topic.strip().lower()

    if topic not in VALID_TOPICS:
        raise ValueError("topic debe ser: enso, jano o 1710")

    if not (1 <= args.priority <= 10):
        raise ValueError("priority debe estar entre 1 y 10")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO accounts_to_watch (handle, topic_hint, author_priority)
    VALUES (?, ?, ?)
    """, (handle, topic, args.priority))

    conn.commit()
    conn.close()

    print(f"✅ Cuenta añadida: @{handle} | topic={topic} | priority={args.priority}")


if __name__ == "__main__":
    main()