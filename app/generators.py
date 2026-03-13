from app.models import ScoredPost
from app.context_loader import load_full_context
from app.ollama_client import generate_json


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

You are NOT a generic social media assistant.
You are writing for a sharp, taste-driven project: 1710Studios.

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
- Do not start with "Agree", "Exactly", "Great point", "Interesting", or similar filler
- Do not mention the author's handle unless truly necessary
- Avoid generic LinkedIn-style writing
- Avoid sounding like a growth coach
- Avoid sounding like a brand account
- Each draft must be specific to the post
- Keep it concise, sharp and intentional
- Sound human, observant and tasteful
- Prefer clarity, context and perspective over agreement
- reply_1 = concise and direct
- reply_2 = slightly more reflective
- quote = standalone quote tweet draft
- new_post = original post inspired by the same idea, not a paraphrase

Length guidance:
- reply_1: 8 to 18 words
- reply_2: 12 to 28 words
- quote: 8 to 24 words
- new_post: 1 to 3 short lines max

Topic-specific guidance:
{topic_style}

Examples of the kind of writing wanted:

Good reply:
"A lot of interfaces are polished but semantically empty."

Good reply:
"We solved access faster than we solved orientation."

Good quote:
"An archive without context is just accumulation."

Good original post:
"Polish became cheap. Meaning didn't."

Good original post:
"Museums do not simply preserve meaning. They frame it."

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


def clean_text(value: str) -> str:
    return (value or "").strip().replace("\n\n\n", "\n\n")


def is_bad_output(text: str) -> bool:
    if not text.strip():
        return True
    for pattern in BANNED_PATTERNS:
        if pattern in text:
            return True
    return False


def fallback_drafts(post: ScoredPost) -> dict:
    if post.topic_hint.lower() == "enso":
        return {
            "reply_1": "The problem is rarely access alone. It is access without enough context to make sense of what is being seen.",
            "reply_2": "Digital culture expanded distribution faster than interpretation. That gap still feels unresolved.",
            "quote": "The archive grew. Context thinned out.",
            "new_post": "A lot of what the internet still lacks is not information, but orientation.",
        }

    if post.topic_hint.lower() == "jano":
        return {
            "reply_1": "Institutions do not just preserve meaning. They shape it.",
            "reply_2": "Neutrality in museums has always been less stable than the display language suggests.",
            "quote": "Every institution frames before it explains.",
            "new_post": "Museums are not neutral containers. They are systems of selection, framing and emphasis.",
        }

    return {
        "reply_1": "Ideas without structure rarely travel far.",
        "reply_2": "The gap is often not imagination, but the system required to carry it.",
        "quote": "Strong ideas collapse inside weak systems.",
        "new_post": "What most projects lack is not ambition, but structure.",
    }


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

        if any(is_bad_output(v) for v in drafts.values()):
            print(f"⚠️ Output flojo detectado para {post.handle}. Usando fallback editorial.")
            return fallback_drafts(post)

        return drafts

    except Exception as e:
        print(f"⚠️ Error generando drafts con Ollama para {post.handle}: {e}")
        return fallback_drafts(post)