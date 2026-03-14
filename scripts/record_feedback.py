import argparse
from app.db import get_connection

VALID_DRAFT_TYPES = {"reply_1", "reply_2", "quote", "new_post"}
VALID_ACTIONS = {"approved", "rejected", "edited", "published"}


def main():
    parser = argparse.ArgumentParser(description="Registrar feedback sobre un borrador")
    parser.add_argument("--draft-id", type=int, required=True, help="ID del draft")
    parser.add_argument(
        "--draft-type",
        type=str,
        required=True,
        help="Tipo: reply_1, reply_2, quote, new_post",
    )
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        help="Acción: approved, rejected, edited, published",
    )
    parser.add_argument("--notes", type=str, default="", help="Notas opcionales")

    args = parser.parse_args()

    if args.draft_type not in VALID_DRAFT_TYPES:
        raise ValueError(
            f"draft_type inválido. Usa uno de: {', '.join(sorted(VALID_DRAFT_TYPES))}"
        )

    if args.action not in VALID_ACTIONS:
        raise ValueError(
            f"action inválida. Usa una de: {', '.join(sorted(VALID_ACTIONS))}"
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM drafts WHERE id = ?", (args.draft_id,))
    draft = cursor.fetchone()

    if not draft:
        conn.close()
        raise ValueError(f"No existe un draft con id {args.draft_id}")

    cursor.execute(
        """
    INSERT INTO feedback (draft_id, draft_type, action, notes)
    VALUES (?, ?, ?, ?)
    """,
        (args.draft_id, args.draft_type, args.action, args.notes),
    )

    conn.commit()
    conn.close()

    print("✅ Feedback guardado correctamente.")


if __name__ == "__main__":
    main()
