import random
import re
from difflib import SequenceMatcher

from app.context_loader import load_full_context
from app.models import ScoredPost
from app.ollama_client import generate_json, generate_text

BANNED_PATTERNS = [
    "#",
    "🔥",
    "🚀",
    "💡",
    "Exactly",
    "exactly",
    "Agree",
    "agree",
    "Great point",
    "great point",
    "Thanks for the thought",
    "Interesting point",
    "interesting point",
]

GENERIC_PHRASES = [
    "context matters more than content",
    "content matters more than aesthetics",
    "design is not just about visuals",
    "quality over buzz",
    "interesting academic opening",
    "documentation simplifies complexity",
    "pkm tools matter more than ever",
    "visuals deceive without meaning",
    "great contrast",
]

LOW_SIGNAL_EXACT_TEXTS = {
    "perfect",
    "multimodal party game",
    "differences in perceived speed",
    "nfts, explained.",
    "keep going.",
    "the life of a designer",
    "the countryside lock-in",
    "retro · cover flow",
    "telegram · header",
}


def clean_handle(handle: str) -> str:
    return (handle or "").lstrip("@")


def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def clean_text(value: str) -> str:
    return (value or "").strip().replace("\n\n\n", "\n\n")


def contains_banned_pattern(text: str) -> bool:
    return any(pattern in text for pattern in BANNED_PATTERNS)


def contains_generic_phrase(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in GENERIC_PHRASES)


def is_too_short(text: str) -> bool:
    words = [w for w in text.split() if w.strip()]
    return len(words) < 5


def is_too_similar_to_post(text: str, post_text: str) -> bool:
    return similarity(text, post_text) >= 0.72


def adds_new_information(text: str, post_text: str) -> bool:
    draft_words = set(normalize_text(text).split())
    post_words = set(normalize_text(post_text).split())
    new_words = draft_words - post_words
    meaningful_new_words = {w for w in new_words if len(w) > 4}
    return len(meaningful_new_words) >= 2


def is_bad_output(text: str, post_text: str = "") -> bool:
    text = (text or "").strip()

    if not text:
        return True

    if contains_banned_pattern(text):
        return True

    if contains_generic_phrase(text):
        return True

    if is_too_short(text):
        return True

    if post_text and is_too_similar_to_post(text, post_text):
        return True

    if post_text and not adds_new_information(text, post_text):
        return True

    return False


def has_enough_text_substance(text: str) -> bool:
    text = (text or "").strip()
    if len(text) < 35:
        return False

    words = [w for w in re.split(r"\s+", text) if w.strip()]
    return len(words) >= 6


def looks_like_low_signal_post(text: str) -> bool:
    normalized = normalize_text(text)

    if normalized in LOW_SIGNAL_EXACT_TEXTS:
        return True

    if len(normalized) < 20:
        return True

    if len(normalized.split()) <= 4:
        return True

    return False


def should_generate_for_post(post: ScoredPost) -> bool:
    text = (post.text or "").strip()

    if not text:
        return False

    if post.score is not None and post.score < 78:
        return False

    if looks_like_low_signal_post(text):
        return False

    if not has_enough_text_substance(text):
        return False

    return True


def fallback_field(post: ScoredPost, field_name: str) -> str:
    topic = (post.topic_hint or "").lower().strip()

    fallback_pool = {
        "enso": {
            "reply_1": [
                "Access scales faster than interpretation.",
                "Abundance is easy. Orientation is harder.",
                "The hard part starts once access is solved.",
            ],
            "reply_2": [
                "A lot of digital abundance still depends on whether people can orient themselves inside it.",
                "Distribution expanded quickly. Interpretation still lags behind.",
                "The missing layer is often not content, but orientation inside it.",
            ],
            "quote": [
                "Access scales fast. Context usually doesn't.",
                "Abundance without orientation quickly becomes noise.",
                "More access does not automatically produce more understanding.",
            ],
            "new_post": [
                "The internet solved distribution faster than interpretation.",
                "Abundance became cheap. Orientation didn't.",
                "The bottleneck is no longer access. It is interpretation.",
            ],
        },
        "jano": {
            "reply_1": [
                "What looks neutral is often just well-framed.",
                "Neutrality often arrives already arranged.",
                "A neutral surface can still hide a strong frame.",
            ],
            "reply_2": [
                "Institutions shape meaning long before they explain it.",
                "Selection and framing happen before interpretation becomes visible.",
                "The framing layer usually starts working before the explanation does.",
            ],
            "quote": [
                "Framing begins before interpretation does.",
                "No institution simply shows. It selects first.",
                "Selection is already a form of argument.",
            ],
            "new_post": [
                "No institution simply displays. It always selects, arranges and frames.",
                "Display is never neutral once selection has already happened.",
                "Curation starts shaping meaning before explanation begins.",
            ],
        },
        "1710": {
            "reply_1": [
                "Strong ideas still need structure to travel well.",
                "A good idea still needs a system around it.",
                "Execution usually breaks where structure is weak.",
            ],
            "reply_2": [
                "A lot of execution problems are really structure problems in disguise.",
                "What looks like inconsistency is often weak structure underneath.",
                "Ideas fail less from ambition than from poor scaffolding.",
            ],
            "quote": [
                "Without structure, good ideas leak energy.",
                "A weak system can waste a strong idea.",
                "Structure decides how far an idea can travel.",
            ],
            "new_post": [
                "Most projects do not fail from lack of ideas. They fail from weak structure.",
                "Execution becomes easier once the structure stops fighting the idea.",
                "A lot of ambition gets lost inside weak systems.",
            ],
        },
    }

    topic_key = topic if topic in fallback_pool else "1710"
    return random.choice(fallback_pool[topic_key][field_name])


def get_topic_style_guide(topic_hint: str) -> str:
    topic = (topic_hint or "").lower().strip()

    if topic == "enso":
        return """
Topic style guide for Ensō:
- Focus on digital culture, systems of meaning, context, curation, interface, archive, internet culture
- Prefer compressed, sharp phrasing
- Sound intellectually precise without sounding academic
- Good words and concepts: context, meaning, structure, orientation, archive, interface, signal, semantics
- Avoid vague inspiration language
- Avoid startup/product cliché language
- Avoid generic design praise
- Prefer conceptual tension over summary
- A good Ensō draft should feel like it reveals a hidden structure in the idea
""".strip()

    if topic == "jano":
        return """
Topic style guide for Jano:
- Focus on institutions, framing, interpretation, selection, display, authority, archives, memory, visual culture
- Replies should feel interpretive, not moralizing
- Good words and concepts: framing, selection, interpretation, institutional voice, display, authority, historical context
- Avoid generic praise of museums or art
- Avoid sounding ideological for the sake of it
- Prefer insight about how meaning is shaped, organized or mediated
- A good Jano draft should make the reader see the institution or artwork differently
""".strip()

    return """
Topic style guide for 1710Studios general:
- Focus on systems, execution, structure, process, discipline, coherence, building
- Sound clear, sharp and grounded
- Good words and concepts: structure, systems, execution, coherence, scaffolding, process
- Avoid sounding promotional
- Avoid sounding like a motivational brand account
- Prefer practical intellectual clarity over slogans
- A good 1710 draft should feel disciplined, calm and structurally sound
""".strip()


def build_prompt(post: ScoredPost) -> str:
    context = load_full_context()
    topic_style = get_topic_style_guide(post.topic_hint)

    return f"""
You are helping Manuel write thoughtful drafts for X.

You are writing for 1710Studios, Ensō and Jano.
The voice is sharp, human, restrained, observant and editorial.

Return ONLY valid JSON with exactly these keys:
{{
  "reply_1": "...",
  "reply_2": "...",
  "quote": "...",
  "new_post": "..."
}}

Hard rules:
- Write in English
- No hashtags
- No emojis
- No praise of the author
- No flattery
- No invented quotes
- Do not mention the author's handle unless truly necessary
- Do not repeat the tweet in cleaner words
- Do not paraphrase the tweet unless you add a clear angle
- Each draft must react to a specific tension, implication, contrast or blind spot in the post
- Stay close to the actual post, not to generic brand themes
- Avoid generic intellectual filler
- Avoid generic social media filler
- Avoid sounding like a growth coach
- Avoid sounding like a brand account
- Avoid turning every post into a statement about archives, systems, context or meaning unless the post really supports it
- Sound human, observant and tasteful
- Prefer specificity over abstraction
- Prefer insight over agreement

Bad outputs to avoid:
- "Context matters more than content."
- "Design is not just about visuals."
- "Quality over buzz."
- "Interesting academic opening."
- "PKM tools matter more than ever."
- "Visuals deceive without meaning."

Field intent:
- reply_1 = concise, natural, publishable reply
- reply_2 = slightly more reflective, but still grounded in the post
- quote = a quote tweet draft with its own angle
- new_post = an original post inspired by the same idea, but more clearly yours

Length guidance:
- reply_1: 7 to 16 words
- reply_2: 10 to 24 words
- quote: 8 to 22 words
- new_post: 1 to 3 short lines max

Topic-specific guidance:
{topic_style}

Examples of the kind of writing wanted:

Good reply:
"The interface got easier. The underlying model got harder to see."

Good reply:
"Access scales quickly. Interpretation usually doesn't."

Good quote:
"Once context collapses, abundance stops feeling like richness."

Good original post:
"Polish became cheap. Orientation didn't."

Good original post:
"A system becomes valuable when it helps you see, not just store."

Brand context:
{context}

Post metadata:
- topic_hint: {post.topic_hint}
- recommended_action: {post.recommended_action}
- priority: {post.priority}
- author: {post.author}
- handle: {post.handle}

Post text:
\"\"\"{post.text}\"\"\"
""".strip()


def build_retry_prompt(post: ScoredPost, field_name: str, bad_text: str) -> str:
    return f"""
Rewrite only one X draft field.

Field:
{field_name}

Original tweet:
\"\"\"{post.text}\"\"\"

Previous weak output:
\"\"\"{bad_text}\"\"\"

Rules:
- Write in English
- Return only the rewritten text
- No JSON
- No hashtags
- No emojis
- No praise
- No flattery
- Do not paraphrase the tweet unless you add a clear angle
- Be specific to the tweet
- Avoid generic intellectual filler
- Avoid vague abstractions unless the tweet clearly supports them
- Keep it concise and natural
- Make it sound human, not branded
""".strip()


def regenerate_field(post: ScoredPost, field_name: str, bad_text: str) -> str:
    prompt = build_retry_prompt(post, field_name, bad_text)

    try:
        result = generate_text(prompt)
        return clean_text(result)
    except Exception as e:
        print(
            f"⚠️ Error regenerando {field_name} para @{clean_handle(post.handle)}: {e}"
        )
        return ""


def repair_drafts(post: ScoredPost, drafts: dict) -> dict:
    repaired = drafts.copy()

    for field_name, value in drafts.items():
        if is_bad_output(value, post.text):
            retry_value = regenerate_field(post, field_name, value)

            if retry_value and not is_bad_output(retry_value, post.text):
                print(
                    f"↻ Campo reparado para @{clean_handle(post.handle)}: {field_name}"
                )
                repaired[field_name] = retry_value
            else:
                print(
                    f"↳ Fallback por campo para @{clean_handle(post.handle)}: {field_name}"
                )
                repaired[field_name] = fallback_field(post, field_name)

    return repaired


def generate_drafts(post: ScoredPost) -> dict:
    prompt = build_prompt(post)

    try:
        result = generate_json(prompt)

        drafts = {
            "reply_1": clean_text(result.get("reply_1", "")),
            "reply_2": clean_text(result.get("reply_2", "")),
            "quote": clean_text(result.get("quote", "")),
            "new_post": clean_text(result.get("new_post", "")),
        }

        return repair_drafts(post, drafts)

    except Exception as e:
        print(
            f"⚠️ Error generando drafts con Ollama para @{clean_handle(post.handle)}: {e}"
        )
        return {
            "reply_1": fallback_field(post, "reply_1"),
            "reply_2": fallback_field(post, "reply_2"),
            "quote": fallback_field(post, "quote"),
            "new_post": fallback_field(post, "new_post"),
        }
