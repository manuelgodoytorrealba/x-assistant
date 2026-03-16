import argparse

from app.db import get_connection

REPLY_MAX_SCORING_AGE_MINUTES = 10080  # 7 días


def clamp(value, min_value=0, max_value=100):
    return max(min_value, min(max_value, value))


def preview_text(text: str, max_len: int = 110) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_post_age(minutes_since_posted):
    if minutes_since_posted is None:
        return "desconocida"

    try:
        minutes = int(minutes_since_posted)
    except (TypeError, ValueError):
        return "desconocida"

    if minutes < 60:
        return f"{minutes} min"

    if minutes < 1440:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} h"
        return f"{hours} h {remaining_minutes} min"

    days = minutes // 1440
    remaining_hours = (minutes % 1440) // 60
    if remaining_hours == 0:
        return f"{days} d"
    return f"{days} d {remaining_hours} h"


def score_topic_relevance(topic_hint: str, text: str) -> float:
    text_lower = (text or "").lower()
    topic = (topic_hint or "").lower()

    keyword_sets = {
        "enso": [
            "culture",
            "internet",
            "interface",
            "context",
            "meaning",
            "archive",
            "digital",
            "signal",
            "knowledge",
            "pkm",
            "obsidian",
            "roam",
            "perception",
            "ai",
            "software",
        ],
        "jano": [
            "museum",
            "art",
            "institution",
            "archive",
            "history",
            "display",
            "framing",
            "visual",
            "exhibition",
            "memory",
        ],
        "1710": [
            "system",
            "structure",
            "process",
            "discipline",
            "execution",
            "building",
            "product",
            "design",
            "workflow",
            "software",
            "ai",
            "market",
            "vendor",
            "lock-in",
            "technology",
            "fashion",
            "music",
            "style",
            "taste",
            "brand",
            "aesthetic",
        ],
    }

    keywords = keyword_sets.get(topic, [])
    matches = sum(1 for kw in keywords if kw in text_lower)

    if matches >= 4:
        return 95
    if matches == 3:
        return 88
    if matches == 2:
        return 78
    if matches == 1:
        return 65

    return 45


def score_early_engagement(minutes_since_posted, likes, replies, reposts) -> float:
    if minutes_since_posted is None:
        return 30

    engagement = (likes or 0) + ((replies or 0) * 2) + ((reposts or 0) * 2)

    if minutes_since_posted <= 60:
        age_factor = 1.0
    elif minutes_since_posted <= 180:
        age_factor = 0.9
    elif minutes_since_posted <= 720:
        age_factor = 0.75
    elif minutes_since_posted <= 1440:
        age_factor = 0.6
    elif minutes_since_posted <= 4320:
        age_factor = 0.45
    elif minutes_since_posted <= 10080:
        age_factor = 0.3
    else:
        age_factor = 0.0

    raw = engagement * age_factor

    if raw >= 100:
        return 95
    if raw >= 50:
        return 85
    if raw >= 20:
        return 72
    if raw >= 8:
        return 60
    if raw >= 3:
        return 48
    return 35


def score_inspiration_signal(minutes_since_posted, likes, replies, reposts) -> float:
    engagement = (likes or 0) + ((replies or 0) * 1.5) + ((reposts or 0) * 2)

    if engagement >= 300:
        base = 92
    elif engagement >= 120:
        base = 84
    elif engagement >= 40:
        base = 76
    elif engagement >= 10:
        base = 66
    elif engagement >= 3:
        base = 58
    else:
        base = 52

    if minutes_since_posted is None:
        return base

    if minutes_since_posted <= 10080:
        return clamp(base + 5)
    if minutes_since_posted <= 43200:  # 30 días
        return base
    if minutes_since_posted <= 129600:  # 90 días
        return clamp(base - 3)

    return clamp(base - 6)


def score_reply_potential(text: str) -> float:
    text = (text or "").strip()
    lower = text.lower()

    if not text:
        return 0

    length = len(text)
    score = 55

    if 80 <= length <= 280:
        score += 18
    elif 40 <= length < 80:
        score += 12
    elif 15 <= length < 40:
        score += 8
    elif length > 280:
        score -= 5
    else:
        score -= 8

    if "?" in text:
        score += 12

    if any(
        token in lower
        for token in [
            "should",
            "why",
            "how",
            "what if",
            "problem",
            "future",
            "design",
            "meaning",
            "culture",
            "system",
            "interface",
            "museum",
            "archive",
            "perception",
            "software",
            "ai",
            "intelligence",
            "internet",
            "technology",
            "tools",
            "market",
            "lock-in",
        ]
    ):
        score += 10

    if length <= 40 and any(ch.isalpha() for ch in text):
        score += 8

    if any(
        bad in lower
        for bad in ["gm", "gn", "lol", "lfg", "🚀", "🔥", "join now", "buy now"]
    ):
        score -= 18

    return clamp(score)


def score_idea_density(text: str) -> float:
    text = (text or "").strip()
    lower = text.lower()

    if not text:
        return 0

    score = 52
    length = len(text)

    if 40 <= length <= 220:
        score += 15
    elif 220 < length <= 500:
        score += 10
    elif 20 <= length < 40:
        score += 8
    elif 8 <= length < 20:
        score += 4
    elif length < 8:
        score -= 10

    if any(
        token in lower
        for token in [
            "because",
            "instead",
            "means",
            "signal",
            "taste",
            "style",
            "culture",
            "design",
            "system",
            "identity",
            "archive",
            "future",
            "internet",
            "software",
            "brand",
            "aesthetic",
            "fashion",
            "music",
            "art",
            "image",
            "look",
            "scene",
            "energy",
            "direction",
            "world",
        ]
    ):
        score += 14

    if ":" in text or "—" in text or "-" in text:
        score += 6

    if "?" in text:
        score += 4

    if any(
        token in lower
        for token in [
            "collection",
            "campaign",
            "directed by",
            "show",
            "season",
            "archive",
            "runway",
            "cover",
            "film",
            "editorial",
            "visual",
            "brand",
        ]
    ):
        score += 8

    if any(bad in lower for bad in ["join now", "buy now", "link in bio"]):
        score -= 18

    return clamp(score)


def decide_action_reply(score: float, reply_potential: float) -> str:
    if score >= 85 and reply_potential >= 70:
        return "reply"
    if score >= 78:
        return "quote"
    if score >= 65:
        return "consider"
    return "ignore"


def decide_action_inspiration(score: float) -> str:
    if score >= 75:
        return "capture"
    if score >= 55:
        return "consider"
    return "ignore"


def decide_priority(score: float) -> str:
    if score >= 85:
        return "alta"
    if score >= 75:
        return "media"
    return "baja"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reply", "inspiration"],
        default="reply",
    )
    args = parser.parse_args()
    mode = args.mode

    conn = get_connection()
    cursor = conn.cursor()

    if mode == "reply":
        cursor.execute(
            """
            UPDATE posts
            SET topic_relevance = NULL,
                early_engagement = NULL,
                reply_potential = NULL,
                score = NULL,
                recommended_action = NULL,
                priority = NULL
            WHERE fetch_mode = ?
              AND (minutes_since_posted IS NULL OR minutes_since_posted > ?)
            """,
            (mode, REPLY_MAX_SCORING_AGE_MINUTES),
        )

        cursor.execute(
            """
            SELECT id, handle, text, topic_hint, minutes_since_posted, likes, replies, reposts
            FROM posts
            WHERE fetch_mode = ?
              AND minutes_since_posted IS NOT NULL
              AND minutes_since_posted <= ?
            ORDER BY id DESC
            """,
            (mode, REPLY_MAX_SCORING_AGE_MINUTES),
        )
    else:
        cursor.execute(
            """
            SELECT id, handle, text, topic_hint, minutes_since_posted, likes, replies, reposts
            FROM posts
            WHERE fetch_mode = ?
            ORDER BY id DESC
            """,
            (mode,),
        )

    rows = cursor.fetchall()

    if not rows:
        conn.commit()
        conn.close()
        print(f"⚠️ No hay posts para puntuar en modo {mode}.")
        return

    scored_rows = []

    for row in rows:
        topic_relevance = score_topic_relevance(row["topic_hint"], row["text"])

        if mode == "reply":
            early_engagement = score_early_engagement(
                row["minutes_since_posted"],
                row["likes"],
                row["replies"],
                row["reposts"],
            )
            reply_potential = score_reply_potential(row["text"])

            final_score = round(
                (topic_relevance * 0.4)
                + (early_engagement * 0.25)
                + (reply_potential * 0.35),
                2,
            )

            recommended_action = decide_action_reply(final_score, reply_potential)
        else:
            early_engagement = score_inspiration_signal(
                row["minutes_since_posted"],
                row["likes"],
                row["replies"],
                row["reposts"],
            )
            reply_potential = score_idea_density(row["text"])

            final_score = round(
                (topic_relevance * 0.40)
                + (early_engagement * 0.20)
                + (reply_potential * 0.40),
                2,
            )

            recommended_action = decide_action_inspiration(final_score)

        priority = decide_priority(final_score)

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
                topic_relevance,
                early_engagement,
                reply_potential,
                final_score,
                recommended_action,
                priority,
                row["id"],
            ),
        )

        scored_rows.append(
            {
                "handle": row["handle"],
                "score": final_score,
                "action": recommended_action,
                "age": format_post_age(row["minutes_since_posted"]),
                "text": preview_text(row["text"]),
            }
        )

    conn.commit()
    conn.close()

    print(f"✅ Posts puntuados correctamente en modo {mode}.")
    for item in scored_rows:
        print(
            f"- {item['handle']} | score={item['score']} | acción={item['action']} | edad={item['age']}"
        )
        print(f"  tweet: {item['text']}")


if __name__ == "__main__":
    main()
