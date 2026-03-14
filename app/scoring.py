from app.models import PostCandidate, ScoredPost


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(value, maximum))


def calculate_topic_relevance(topic_hint: str) -> float:
    mapping = {
        "jano": 90,
        "enso": 95,
        "1710": 85,
    }
    return mapping.get(topic_hint.lower(), 50)


def calculate_early_engagement(post: PostCandidate) -> float:
    weighted = (post.likes * 1.0) + (post.replies * 2.0) + (post.reposts * 1.5)
    freshness_bonus = max(0, 60 - post.minutes_since_posted)
    score = weighted * 0.6 + freshness_bonus
    return clamp(score)


def calculate_reply_potential(post: PostCandidate) -> float:
    text = post.text.lower()

    signals = 0
    if "but" in text:
        signals += 20
    if "should" in text:
        signals += 15
    if "problem" in text:
        signals += 15
    if "culture" in text:
        signals += 15
    if "internet" in text:
        signals += 15
    if post.replies > 50:
        signals -= 20  # demasiado saturado
    if post.minutes_since_posted < 20:
        signals += 15

    return clamp(40 + signals)


def recommend_action(score: float, reply_potential: float) -> str:
    if score >= 85 and reply_potential >= 70:
        return "reply"
    if score >= 75:
        return "quote"
    if score >= 60:
        return "consider"
    return "ignore"


def priority_label(score: float) -> str:
    if score >= 85:
        return "alta"
    if score >= 70:
        return "media"
    return "baja"


def score_post(post: PostCandidate) -> ScoredPost:
    topic_relevance = calculate_topic_relevance(post.topic_hint)
    early_engagement = calculate_early_engagement(post)
    reply_potential = calculate_reply_potential(post)

    total_score = (
        topic_relevance * 0.40
        + early_engagement * 0.25
        + (post.author_priority * 10) * 0.20
        + reply_potential * 0.15
    )

    total_score = round(clamp(total_score), 2)

    return ScoredPost(
        **post.model_dump(),
        topic_relevance=round(topic_relevance, 2),
        early_engagement=round(early_engagement, 2),
        reply_potential=round(reply_potential, 2),
        score=total_score,
        recommended_action=recommend_action(total_score, reply_potential),
        priority=priority_label(total_score),
    )
