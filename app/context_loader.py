from app.config import CONTEXT_DIR


def load_context_file(filename: str) -> str:
    path = CONTEXT_DIR / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_full_context() -> str:
    files = [
        "1710_voice.md",
        "jano_context.md",
        "enso_context.md",
        "do_not_sound_like.md",
    ]
    parts = []

    for filename in files:
        content = load_context_file(filename)
        if content.strip():
            parts.append(f"## {filename}\n{content.strip()}")

    return "\n\n".join(parts)
