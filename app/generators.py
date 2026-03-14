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
    text = (value or "").strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace('"""', '"').replace("'''", "'")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_banned_pattern(text: str) -> bool:
    return any(pattern in text for pattern in BANNED_PATTERNS)


def contains_generic_phrase(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in GENERIC_PHRASES)


def is_too_short(text: str) -> bool:
    words = [w for w in text.split() if w.strip()]
    return len(words) < 4


def is_too_similar_to_post(text: str, post_text: str) -> bool:
    return similarity(text, post_text) >= 0.72


def adds_new_information(text: str, post_text: str) -> bool:
    draft_words = set(normalize_text(text).split())
    post_words = set(normalize_text(post_text).split())
    new_words = draft_words - post_words
    meaningful_new_words = {w for w in new_words if len(w) > 4}
    return len(meaningful_new_words) >= 2


def has_fake_quote_format(text: str) -> bool:
    stripped = text.strip()

    if stripped.startswith('"') and stripped.endswith('"'):
        return True

    if stripped.startswith("'") and stripped.endswith("'"):
        return True

    if stripped.startswith("“") and stripped.endswith("”"):
        return True

    if "— @" in stripped or "- @" in stripped:
        return True

    if "— " in stripped and len(stripped.split("—")[-1].strip().split()) <= 3:
        return True

    if " - " in stripped and len(stripped.split(" - ")[-1].strip().split()) <= 3:
        return True

    return False


def has_suspicious_attribution(text: str) -> bool:
    lowered = normalize_text(text)

    suspicious_patterns = [
        "- socrates",
        "— socrates",
        "- plato",
        "— plato",
        "- aristotle",
        "— aristotle",
        "- nietzsche",
        "— nietzsche",
        "- kafka",
        "— kafka",
        "- john zerzan",
        "— john zerzan",
        "- marshall mcluhan",
        "— marshall mcluhan",
        "- alan kay",
        "— alan kay",
    ]

    return any(pattern in lowered for pattern in suspicious_patterns)


def is_overly_literal_reply(text: str, post_text: str) -> bool:
    if not post_text:
        return False

    norm_text = normalize_text(text)
    norm_post = normalize_text(post_text)

    if norm_text in norm_post:
        return True

    if similarity(text, post_text) >= 0.82:
        return True

    return False


def has_ai_sounding_abstraction(text: str) -> bool:
    lowered = normalize_text(text)

    weak_patterns = [
        "true design excellence",
        "transformative power",
        "foundational elements falter",
        "underlying principles",
        "revealing hidden layers",
        "redefines the narrative",
        "intellectual landscape",
        "coherent action",
        "making ideas actionable",
        "the essence of human thought",
        "human context still matter",
        "the value lies in",
        "will matter in an ai-driven world",
        "the true value lies",
        "subtly but profoundly",
    ]

    return any(pattern in lowered for pattern in weak_patterns)


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

    if has_fake_quote_format(text):
        return True

    if has_suspicious_attribution(text):
        return True

    if has_ai_sounding_abstraction(text):
        return True

    if post_text and is_too_similar_to_post(text, post_text):
        return True

    if post_text and is_overly_literal_reply(text, post_text):
        return True

    if post_text and not adds_new_information(text, post_text):
        return True

    return False


def has_enough_text_substance(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return False

    words = [w for w in re.split(r"\s+", text) if w.strip()]
    lower = text.lower()

    # Tweets largos normales
    if len(text) >= 35 and len(words) >= 6:
        return True

    # Permitir aforismos / tesis cortas pero potentes
    strong_short_tokens = [
        "ai",
        "software",
        "market",
        "future",
        "system",
        "design",
        "technology",
        "internet",
        "tools",
        "moat",
        "moats",
        "vendor",
        "lock-in",
    ]

    if len(text) >= 15 and any(token in lower for token in strong_short_tokens):
        return True

    return False


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
    return get_skip_reason(post) is None


def fallback_field(post: ScoredPost, field_name: str) -> str:
    topic = (post.topic_hint or "").lower().strip()
    text = (post.text or "").lower()

    fallback_pool = {
        # ENSŌ = cultura digital / internet / sentido / archivo / PKM
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
        # JANO = arte / museos / instituciones / framing / memoria / curaduría
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
        # 1710 GENERAL = sistemas / ejecución / estructura
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
        # 1710 AI / SOFTWARE / MARKET
        "1710_ai_software": {
            "reply_1": [
                "The moat shifts once intelligence becomes infrastructure.",
                "When intelligence gets cheaper, distribution matters more.",
                "AI compresses the value of software into thinner layers.",
            ],
            "reply_2": [
                "As AI lowers implementation cost, advantage shifts toward workflow, trust and distribution.",
                "Software stops being the moat once intelligence becomes widely embedded.",
                "When intelligence spreads across the stack, value moves upward.",
            ],
            "quote": [
                "AI does not remove moats. It relocates them.",
                "When intelligence gets cheaper, the moat moves higher in the stack.",
                "The software layer gets thinner when intelligence becomes infrastructure.",
            ],
            "new_post": [
                "When intelligence becomes cheap, the moat moves from code to distribution.",
                "AI compresses the software layer and expands the value of workflow and trust.",
                "The real shift with AI is not capability. It is where value accumulates.",
            ],
        },
    }

    if topic == "1710":
        topic_key = detect_1710_subtopic(text)
    else:
        topic_key = topic if topic in fallback_pool else "1710"

    return random.choice(fallback_pool[topic_key][field_name])


def detect_1710_subtopic(text: str) -> str:
    lower = (text or "").lower()

    ai_software_keywords = [
        "ai",
        "software",
        "moat",
        "moats",
        "market",
        "vendor",
        "lock-in",
        "lockin",
        "tool",
        "tools",
        "model",
        "models",
        "automation",
        "workflow",
        "distribution",
        "interface",
        "code",
        "product",
        "api",
        "apis",
        "agent",
        "agents",
        "stack",
        "platform",
        "platforms",
    ]

    if any(word in lower for word in ai_software_keywords):
        return "1710_ai_software"

    return "1710"


def get_effective_subtopic(post: ScoredPost) -> str:
    topic = (post.topic_hint or "").lower().strip()

    if topic == "1710":
        return detect_1710_subtopic(post.text)

    return topic


def get_topic_style_guide(post: ScoredPost) -> str:
    subtopic = get_effective_subtopic(post)

    if subtopic == "enso":
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
- Good replies often contrast access vs interpretation, abundance vs orientation, interface vs meaning
""".strip()

    if subtopic == "jano":
        return """
Topic style guide for Jano:
- Focus on art, institutions, framing, interpretation, selection, display, authority, archives, memory, visual culture
- Replies should feel interpretive, not moralizing
- Good words and concepts: framing, selection, interpretation, institutional voice, display, authority, historical context, curatorship
- Avoid generic praise of museums or art
- Avoid sounding ideological for the sake of it
- Prefer insight about how meaning is shaped, organized or mediated
- A good Jano draft should make the reader see the institution, artwork or act of display differently
- Good replies often point to framing, curatorial choice, institutional voice, historical arrangement
""".strip()

    if subtopic == "1710_ai_software":
        return """
Topic style guide for 1710Studios / AI / software / market:
- Focus on software, AI, markets, distribution, workflow, product layers, interfaces, incentives, moats, infrastructure
- Sound sharp, strategic and grounded
- Good words and concepts: moat, distribution, workflow, stack, infrastructure, interface, implementation, trust, market structure, aggregation
- Prefer concrete shifts in value, not vague philosophy
- Avoid generic "humanity vs AI" language
- Avoid "context still matters" unless directly justified by the tweet
- Avoid abstract motivational language
- A good draft should identify where value is moving: from code to distribution, from implementation to workflow, from product to interface, from software to infrastructure
- Good replies often point to changing moats, thinner software layers, cheaper implementation, and higher-level distribution advantages
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
    topic_style = get_topic_style_guide(post)
    effective_subtopic = get_effective_subtopic(post)

    extra_examples = ""

    if effective_subtopic == "1710_ai_software":
        extra_examples = """
Examples especially relevant here:

Good reply:
"The moat moves up the stack once implementation gets cheaper."

Good reply:
"AI makes software easier to build, not easier to defend."

Good quote:
"When intelligence gets cheaper, distribution matters more."

Good original post:
"AI doesn't kill moats. It relocates them."

Good original post:
"As implementation gets commoditized, workflow becomes the product."
""".strip()

    elif effective_subtopic == "jano":
        extra_examples = """
Examples especially relevant here:

Good reply:
"What looks neutral is usually just well-arranged."

Good reply:
"Display is already a form of interpretation."

Good quote:
"Institutions shape attention before they shape memory."

Good original post:
"A museum does not simply preserve culture. It frames it."

Good original post:
"Selection is not neutral just because it is quiet."
""".strip()

    elif effective_subtopic == "enso":
        extra_examples = """
Examples especially relevant here:

Good reply:
"The interface got easier. The underlying model got harder to see."

Good reply:
"Abundance scales faster than interpretation."

Good quote:
"Once context collapses, access stops feeling like richness."

Good original post:
"Abundance became cheap. Orientation didn't."

Good original post:
"The archive grows faster than the reader's ability to navigate it."
""".strip()

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
- If the post is about AI/software/markets, speak in terms of value shift, moats, workflow, distribution, product layers or infrastructure
- If the post is about art/institutions, speak in terms of framing, display, authority, curation or interpretation
- If the post is about digital culture/internet/interface, speak in terms of orientation, meaning, archive, interface or context

Bad outputs to avoid:
- "Context matters more than content."
- "Design is not just about visuals."
- "Quality over buzz."
- "Interesting academic opening."
- "PKM tools matter more than ever."
- "Visuals deceive without meaning."
- "Human context still matters."
- "The essence of human thought still matters."

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

Effective subtopic:
{effective_subtopic}

Topic-specific guidance:
{topic_style}

General examples of the kind of writing wanted:

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

{extra_examples}

Brand context:
{context}

Post metadata:
- topic_hint: {post.topic_hint}
- effective_subtopic: {effective_subtopic}
- recommended_action: {post.recommended_action}
- priority: {post.priority}
- author: {post.author}
- handle: {post.handle}
- url: {post.url}

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
- No invented quotes
- No fake attribution
- Do not add author handles
- Do not add philosopher names
- Do not wrap the answer in quotation marks
- Do not sound like a thought-leadership post
- Avoid generic "humanity / context / essence" language
- Be concrete and specific to the tweet
- Prefer market, software, product, systems, distribution, incentives, lock-in, interface, execution
- Keep it concise and natural
- Make it sound human, sharp and grounded
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


def get_skip_reason(post: ScoredPost):
    text = (post.text or "").strip()

    if not text:
        return "sin texto"

    # Alineado con score_posts.py: hasta 7 días
    if post.minutes_since_posted is not None and post.minutes_since_posted > 10080:
        return f"demasiado viejo ({post.minutes_since_posted} min)"

    # No volver a filtrar por score aquí.
    # El score ya se filtra en generate_drafts.py con SQL.

    if looks_like_low_signal_post(text):
        return "post de baja señal"

    if not has_enough_text_substance(text):
        return "sin suficiente sustancia"

    return None
