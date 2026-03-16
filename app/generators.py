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
    "seasonality matters in marketing",
    "optimizing release timing for impact",
    "track user satisfaction metrics",
    "repeat business",
    "brand exposure",
    "luxury materials in modern designs",
    "strategic use of music",
    "emerging talent impacts the ecosystem",
    "how do unconventional choices impact brand perception",
    "tune in now",
    "live updates and exclusive music",
    "new metals collection launched today",
    "tickets to philly await",
    "elevating eyewear with premium materials",
    "for more",
    "perfect for the season",
    "high-end materials",
    "limited edition launch",
    "now available",
    "don't miss",
    "dont miss",
    "stay tuned",
    "premium eyewear",
    "exclusive music",
    "tickets to",
    "new collection",
    "live updates",
    "limited drop",
    "available now",
    "shop now",
    "tap in",
    "out now",
    "coming soon",
    "must-have",
    "elevating your",
    "crafted for",
    "designed for",
    "customer satisfaction",
    "launch cycles",
    "product launch",
    "marketing strategy",
    "brand strategy",
    "business growth",
]

PROMO_PATTERNS = [
    r"\bnow available\b",
    r"\bdon[’']?t miss\b",
    r"\bstay tuned\b",
    r"\bshop now\b",
    r"\bout now\b",
    r"\bcoming soon\b",
    r"\blimited edition\b",
    r"\blimited drop\b",
    r"\bnew collection\b",
    r"\btickets to\b",
    r"\blive updates\b",
    r"\bperfect for\b",
    r"\bpremium materials?\b",
    r"\bhigh-end materials?\b",
    r"\bexclusive music\b",
    r"\belevating\b",
    r"\bfor more\b",
    r"\bmust-have\b",
    r"\bcrafted for\b",
    r"\bdesigned for\b",
]

CORPORATE_OR_ACADEMIC_PATTERNS = [
    r"\bsynergy\b",
    r"\binnovation\b",
    r"\bvisibility\b",
    r"\bmomentum\b",
    r"\bbrand enthusiasm\b",
    r"\bbrand excitement\b",
    r"\bcustomer joy\b",
    r"\bcustomer satisfaction\b",
    r"\bgenuine feedback\b",
    r"\bgenuine sentiment\b",
    r"\bstrategic implication\b",
    r"\bstrategic\b",
    r"\bmarketing\b",
    r"\bconsumer\b",
    r"\bcustomer\b",
    r"\bstatement piece\b",
    r"\bintersection of\b",
    r"\bredefine\b",
    r"\bcutting-edge\b",
    r"\bunique aesthetic experience\b",
    r"\bvisual strategies\b",
    r"\bvalue reevaluation\b",
    r"\bworth noting\b",
    r"\btrue strength lies in\b",
    r"\bdivine judgment\b",
    r"\bexplore the\b",
    r"\bhow [a-z\s]+ captures\b",
    r"\bthe interplay of\b",
    r"\bthe tension between\b",
    r"\ba fresh lens on\b",
    r"\badds unexpected depth\b",
    r"\badds depth\b",
    r"\bfleeting beauty\b",
    r"\bbeauty in the momentary\b",
    r"\bshape culture\b",
    r"\brepeat visit\b",
    r"\bmasked in casual approval\b",
    r"\bshift in agency and identity\b",
    r"\bnot just\b",
    r"\bmatters in\b",
    r"\bcan make or break\b",
    r"\boptimize for\b",
    r"\bpeaks in\b",
    r"\breveal membership codes\b",
]

MARKETING_VERB_PATTERNS = [
    r"\bhighlight(?:ing)?\b",
    r"\bexplore\b",
    r"\bcapture the\b",
    r"\buse urgency\b",
    r"\bdrive awareness\b",
    r"\bdrive interest\b",
    r"\bdrive visibility\b",
    r"\bredefine(?:s|d)?\b",
    r"\bchallenge(?:s|d)?\b",
    r"\bposition(?:s|ed)?\b",
    r"\bframe(?:s|d)? as\b",
    r"\belevate(?:s|d)?\b",
    r"\bsignal(?:s|ed)? user satisfaction\b",
    r"\bemphasize(?:s|d)?\b",
    r"\bshow(?:s|ing)? trust and satisfaction\b",
    r"\breinforc(?:e|es|ed)\b",
    r"\bhold the key\b",
    r"\bgame-changer\b",
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

SUSPICIOUS_ATTRIBUTION_NAMES = [
    "socrates",
    "plato",
    "aristotle",
    "nietzsche",
    "kafka",
    "john zerzan",
    "marshall mcluhan",
    "alan kay",
    "elon musk",
    "steve jobs",
    "picasso",
    "warhol",
    "kanye",
    "virgil",
]

LATIN_CHAR_RE = re.compile(r"[A-Za-zÀ-ÿ]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30FF]")
HANGUL_RE = re.compile(r"[\uAC00-\uD7AF]")


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
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip()
    return text


def contains_banned_pattern(text: str) -> bool:
    return any(pattern in text for pattern in BANNED_PATTERNS)


def contains_generic_phrase(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in GENERIC_PHRASES)


def contains_promo_language(text: str) -> bool:
    normalized = normalize_text(text)
    return any(re.search(pattern, normalized) for pattern in PROMO_PATTERNS)


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
    stripped = (text or "").strip()

    if not stripped:
        return False

    if stripped.startswith('"') and stripped.endswith('"'):
        return True

    if stripped.startswith("'") and stripped.endswith("'"):
        return True

    if stripped.startswith("“") and stripped.endswith("”"):
        return True

    if stripped.startswith("‘") and stripped.endswith("’"):
        return True

    if "— @" in stripped or "- @" in stripped:
        return True

    if re.search(r'[“"][^"\n]{6,}[”"]\s*(?:—|-)\s*\w+', stripped):
        return True

    if re.search(
        r"(?:^|\s)(?:once said|once warned|said:|wrote:|according to)\b",
        normalize_text(stripped),
    ):
        return True

    if "— " in stripped and len(stripped.split("—")[-1].strip().split()) <= 4:
        return True

    if " - " in stripped and len(stripped.split(" - ")[-1].strip().split()) <= 4:
        return True

    if re.search(r'^[\'"`“].+[\'"`”]\.?$', stripped):
        return True

    return False


def has_suspicious_attribution(text: str) -> bool:
    lowered = normalize_text(text)

    for name in SUSPICIOUS_ATTRIBUTION_NAMES:
        patterns = [
            f"- {name}",
            f"— {name}",
            f'" {name}',
            f"' {name}",
            f"according to {name}",
            f"{name} once said",
            f"{name} once warned",
            f"{name} said",
            f"{name} wrote",
        ]
        if any(pattern in lowered for pattern in patterns):
            return True

    return False


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
        "unlocking new possibilities",
        "drives engagement",
        "elevates the experience",
        "resonates with audiences",
        "creates impact at scale",
        "strategic implication",
        "thought leadership",
        "future-forward",
    ]

    return any(pattern in lowered for pattern in weak_patterns)


def has_corporate_or_academic_tone(text: str) -> bool:
    lowered = normalize_text(text)

    if any(re.search(pattern, lowered) for pattern in CORPORATE_OR_ACADEMIC_PATTERNS):
        return True

    weak_phrases = [
        "focus on",
        "highlight the",
        "explore the",
        "worth noting",
        "adds depth",
        "captures fleeting beauty",
        "the interplay of",
        "the tension between",
        "fresh lens",
        "redefine the intersection",
        "statement piece",
        "cultural insiders",
        "exclusive social markers",
        "genuine sentiment",
        "visual strategies",
        "seasonal timing matters",
        "marketing momentum",
        "brand's raw edge",
        "brand excitement",
        "customer joy",
    ]

    if any(phrase in lowered for phrase in weak_phrases):
        return True

    suspicious_templates = [
        r"^[A-Z][a-z]+(?: [a-z]+){0,6} matters(?: [a-z]+){0,6}\.$",
        r"^[A-Z][a-z]+(?: [a-z]+){0,6} becomes(?: [a-z]+){0,6}\.$",
        r"^[A-Z][a-z]+(?: [a-z]+){0,6} reveals(?: [a-z]+){0,6}\.$",
        r"^[A-Z][a-z]+(?: [a-z]+){0,6} reflects(?: [a-z]+){0,6}\.$",
        r"^[A-Z][a-z]+(?: [a-z]+){0,6} signals(?: [a-z]+){0,6}\.$",
    ]

    stripped = (text or "").strip()
    if any(re.match(pattern, stripped) for pattern in suspicious_templates):
        return True

    abstract_nouns = [
        "synergy",
        "innovation",
        "visibility",
        "momentum",
        "beauty",
        "depth",
        "experience",
        "intersection",
        "enthusiasm",
        "sentiment",
        "priority",
        "values",
        "strength",
    ]
    words = re.findall(r"\b[a-z]+\b", lowered)
    abstract_hits = sum(1 for w in words if w in abstract_nouns)
    if abstract_hits >= 2 and len(words) <= 14:
        return True

    return False


def has_marketing_verb_structure(text: str) -> bool:
    lowered = normalize_text(text)

    if any(re.search(pattern, lowered) for pattern in MARKETING_VERB_PATTERNS):
        return True

    bad_starts = [
        "highlight ",
        "explore ",
        "capture ",
        "use ",
        "drive ",
        "position ",
        "frame ",
        "elevate ",
        "challenge ",
        "emphasize ",
        "documenting ",
        "understanding ",
    ]

    stripped = lowered.strip()
    if any(stripped.startswith(prefix) for prefix in bad_starts):
        return True

    bad_phrases = [
        "use urgency to",
        "drive collection awareness",
        "user experience is key",
        "trust and satisfaction",
        "cultural relevance",
        "personal connection",
        "what's next",
        "frame the event",
        "signal user satisfaction",
        "challenge societal norms",
        "capture the essence",
        "unexpected beauty",
        "everyday style",
    ]

    return any(phrase in lowered for phrase in bad_phrases)


def has_non_latin_noise(text: str) -> bool:
    if not text:
        return False

    has_latin = bool(LATIN_CHAR_RE.search(text))
    has_cyrillic = bool(CYRILLIC_RE.search(text))
    has_cjk = bool(CJK_RE.search(text))
    has_japanese = bool(HIRAGANA_KATAKANA_RE.search(text))
    has_hangul = bool(HANGUL_RE.search(text))

    if has_latin and (has_cyrillic or has_cjk or has_japanese or has_hangul):
        return True

    if not has_latin and (has_cyrillic or has_cjk or has_japanese or has_hangul):
        return True

    return False


def has_suspicious_unicode_mix(text: str) -> bool:
    if not text:
        return False

    suspicious_mixed_word = re.search(
        r"[A-Za-zÀ-ÿ]+[\u0400-\u04FF][A-Za-zÀ-ÿ]+|[\u0400-\u04FF]+[A-Za-zÀ-ÿ]+|[A-Za-zÀ-ÿ]+[\u3400-\u9FFF]+",
        text,
    )
    return suspicious_mixed_word is not None


def is_promo_heavy_source(text: str) -> bool:
    normalized = normalize_text(text)

    promo_hits = 0

    promo_keywords = [
        "out now",
        "tickets",
        "tune in",
        "today only",
        "special price",
        "collection",
        "available",
        "shop",
        "link",
        "drop",
        "radio",
        "mixtape",
        "shout out",
        "fashion show",
    ]

    promo_hits += sum(1 for keyword in promo_keywords if keyword in normalized)

    if "http" in (text or "").lower():
        promo_hits += 1

    if (text or "").count("!") >= 3:
        promo_hits += 1

    uppercase_words = re.findall(r"\b[A-Z]{3,}\b", text or "")
    if len(uppercase_words) >= 3:
        promo_hits += 1

    return promo_hits >= 2


def should_force_minimal_inspiration(post: ScoredPost) -> bool:
    text = (post.text or "").strip()
    normalized = normalize_text(text)

    if not text:
        return False

    if is_promo_heavy_source(text):
        return True

    if len(normalized) <= 80:
        if len(normalized.split()) <= 8:
            return True

    if text.count("!") >= 3:
        return True

    if (
        re.search(r"\b[A-Z]{4,}\b", text)
        and len(re.findall(r"\b[A-Z]{4,}\b", text)) >= 2
    ):
        return True

    return False


def is_bad_output(text: str, post_text: str = "", mode: str = "reply") -> bool:
    text = (text or "").strip()

    if not text:
        return True

    if contains_banned_pattern(text):
        return True

    if contains_generic_phrase(text):
        return True

    if contains_promo_language(text):
        return True

    if is_too_short(text):
        return True

    if has_fake_quote_format(text):
        return True

    if has_suspicious_attribution(text):
        return True

    if has_ai_sounding_abstraction(text):
        return True

    if mode == "inspiration" and has_corporate_or_academic_tone(text):
        return True

    if mode == "inspiration" and has_marketing_verb_structure(text):
        return True

    if has_non_latin_noise(text):
        return True

    if has_suspicious_unicode_mix(text):
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

    if len(text) >= 35 and len(words) >= 6:
        return True

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


def should_generate_for_post(post: ScoredPost, mode: str = "reply") -> bool:
    return get_skip_reason(post, mode=mode) is None


def fallback_field(post: ScoredPost, field_name: str, mode: str = "reply") -> str:
    topic = (post.topic_hint or "").lower().strip()
    text = (post.text or "").lower()

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

    inspiration_fallback_pool = {
        "enso": {
            "reply_1": [
                "The signal is less about content than about how it gets framed.",
                "There is a clear orientation problem sitting underneath the surface.",
                "What matters here is the model of attention, not the object itself.",
            ],
            "reply_2": [
                "The stronger read is not the statement itself, but the interface, context or filtering logic around it.",
                "There is a usable frame here about how digital culture compresses meaning while expanding access.",
                "This can be reused as a signal about taste, mediation and how people navigate abundance.",
            ],
            "quote": [
                "Abundance keeps growing. Orientation remains the rarer layer.",
                "The interface makes access easier and interpretation thinner.",
                "The archive expands faster than anyone's ability to read it well.",
            ],
            "new_post": [
                "Abundance became cheap.\nOrientation didn't.",
                "The interface solved access.\nIt did not solve meaning.",
                "A large archive is useless if no one can feel the frame inside it.",
            ],
        },
        "jano": {
            "reply_1": [
                "The frame is doing more work here than the object itself.",
                "This reads like a lesson in selection before interpretation.",
                "What looks neutral already carries a curatorial choice.",
            ],
            "reply_2": [
                "The useful angle is how display, sequencing or institutional voice quietly shapes what feels legible.",
                "There is a strong editorial read here about how authority hides inside arrangement.",
                "The signal is not just the artwork or reference, but the structure that makes it appear coherent.",
            ],
            "quote": [
                "Selection is already an argument, even when it looks quiet.",
                "Display rarely arrives neutral. The frame gets there first.",
                "Institutions shape meaning long before they explain it.",
            ],
            "new_post": [
                "Nothing is shown without being arranged first.",
                "The frame often lands before the explanation does.",
                "A display can look neutral and still make a very specific argument.",
            ],
        },
        "1710": {
            "reply_1": [
                "There is a stronger frame here than the post says directly.",
                "The useful part is the signal underneath the statement.",
                "This reads more like positioning than opinion.",
            ],
            "reply_2": [
                "The interesting move is to extract the structure, taste or strategic frame hiding under the surface phrasing.",
                "This could become a sharper 1710 post once the underlying signal is separated from the immediate take.",
                "The post matters less as commentary than as evidence of what kind of frame is gaining traction.",
            ],
            "quote": [
                "A signal becomes useful once you can name the frame behind it.",
                "Taste often reveals structure before analysis catches up.",
                "The interesting part is not the opinion. It is the position underneath it.",
            ],
            "new_post": [
                "A lot of cultural signal arrives before people have language for it.",
                "The frame matters most when it is still hard to name.",
                "Good positioning often starts as a feeling before it becomes a sentence.",
            ],
        },
        "1710_ai_software": {
            "reply_1": [
                "This points to a shift in where leverage is accumulating.",
                "The useful signal is where value is moving, not the feature itself.",
                "The frame here is about stack position, not novelty.",
            ],
            "reply_2": [
                "The stronger read is about where advantage migrates once implementation gets cheaper and interfaces get crowded.",
                "This can be reused as a signal about workflow, trust, distribution or the thinning of the software layer.",
                "The interesting part is not the tool itself but the market structure it implies upstream.",
            ],
            "quote": [
                "When implementation gets cheaper, value moves somewhere else.",
                "AI does not flatten value. It changes where the leverage sits.",
                "The real signal is which layer becomes harder to commoditize.",
            ],
            "new_post": [
                "As implementation gets cheaper,\nvalue moves higher in the stack.",
                "A cheaper model does not erase moats.\nIt relocates them.",
                "The important shift is not capability.\nIt is where leverage starts to concentrate.",
            ],
        },
    }

    minimal_inspiration_pool = {
        "1710": {
            "reply_1": [
                "The signal sits underneath the obvious statement.",
                "This reads more like a taste marker than a take.",
                "The frame matters more than the wording here.",
            ],
            "reply_2": [
                "There is probably a stronger frame hiding underneath the surface language here.",
                "Useful signal, but only once you strip out the immediate caption layer.",
                "The post works better as a marker of scene logic than as literal commentary.",
            ],
            "quote": [
                "The signal gets clearer once the frame is separated from the promo.",
                "Interesting less for what it says than for what it signals.",
                "The surface is loud. The frame underneath is quieter.",
            ],
            "new_post": [
                "A lot of cultural signal arrives disguised as announcement.",
                "The loudest layer is rarely the most interesting one.",
                "Sometimes the frame is better than the caption.",
            ],
        },
        "1710_ai_software": {
            "reply_1": [
                "The useful part is where leverage is moving.",
                "This is more about stack position than novelty.",
                "The signal is upstream from the feature.",
            ],
            "reply_2": [
                "The stronger read is not the feature itself but the layer gaining defensibility.",
                "Useful once you strip it down to where leverage is starting to accumulate.",
                "The post matters less literally than as a marker of where value may be shifting.",
            ],
            "quote": [
                "The real signal is which layer gets harder to commoditize.",
                "Implementation gets cheaper. Leverage moves.",
                "The feature is surface. The stack shift is the real story.",
            ],
            "new_post": [
                "When implementation gets cheaper,\nvalue looks for a new home.",
                "The surface product changes fast.\nThe leverage shift matters more.",
                "The interesting part is not the feature.\nIt is the layer gaining power.",
            ],
        },
    }

    if topic == "1710":
        topic_key = detect_1710_subtopic(text)
    else:
        topic_key = topic if topic in fallback_pool else "1710"

    if mode == "inspiration" and should_force_minimal_inspiration(post):
        minimal_topic_key = (
            topic_key if topic_key in minimal_inspiration_pool else "1710"
        )
        return random.choice(minimal_inspiration_pool[minimal_topic_key][field_name])

    if mode == "inspiration":
        pool = inspiration_fallback_pool
    else:
        pool = fallback_pool

    topic_pool = pool.get(topic_key, pool["1710"])
    return random.choice(topic_pool[field_name])


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


def build_reply_prompt(post: ScoredPost) -> str:
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


def build_inspiration_prompt(post: ScoredPost) -> str:
    context = load_full_context()
    topic_style = get_topic_style_guide(post)
    effective_subtopic = get_effective_subtopic(post)
    minimal_mode = should_force_minimal_inspiration(post)

    extra_examples = ""

    if effective_subtopic == "1710_ai_software":
        extra_examples = """
Examples especially relevant here:

Good observation:
"This points to a shift in where leverage is accumulating."

Good angle:
"The real read is not the feature, but the layer of the stack gaining pricing power."

Good quote:
"When implementation gets cheaper, value migrates."

Good post seed:
"As software gets easier to produce,
distribution and workflow become easier to defend."
""".strip()
    elif effective_subtopic == "jano":
        extra_examples = """
Examples especially relevant here:

Good observation:
"The frame is doing more work here than the object itself."

Good angle:
"This can be reused as a read on how authority hides inside display and sequence."

Good quote:
"Selection is already an argument."

Good post seed:
"A display can look neutral
and still make a very specific claim."
""".strip()
    elif effective_subtopic == "enso":
        extra_examples = """
Examples especially relevant here:

Good observation:
"The signal sits in the interface logic, not just in the post itself."

Good angle:
"This is useful as a read on orientation, filtering and how digital culture compresses meaning."

Good quote:
"Abundance keeps scaling. Orientation does not."

Good post seed:
"The interface solved access.
It did not solve meaning."
""".strip()
    else:
        extra_examples = """
Examples especially relevant here:

Good observation:
"This feels more like positioning than opinion."

Good angle:
"The useful move is to name the frame underneath the statement, not to repeat the statement."

Good quote:
"The signal matters once the frame becomes legible."

Good post seed:
"Good positioning often starts as a feeling
before it becomes a sentence."
""".strip()

    minimal_mode_rules = ""
    if minimal_mode:
        minimal_mode_rules = """
Minimal mode is ON for this source.

Additional rules for minimal mode:
- Keep everything more compressed than usual
- Do not inflate a short, promo-heavy or coded source into a theory
- Do not explain too much
- Prefer one clean frame over multiple ideas
- observation should feel like a signal note, not analysis
- angle should stay short and restrained
- quote should be lean and publishable
- new_post should be sparse and sharp
- If the source is basically an announcement, extract the ritual, aura, taste code or distribution logic behind it
- Never rewrite the announcement itself
""".strip()

    return f"""
You are helping Manuel extract inspiration signals for 1710Studios from X posts.

The goal is NOT to reply directly.
The goal is to extract:
- the interesting observation
- the hidden angle
- a strong quote-tweet possibility
- a usable original post seed

Return ONLY valid JSON with exactly these keys:
{{
  "reply_1": "...",
  "reply_2": "...",
  "quote": "...",
  "new_post": "..."
}}

Interpret the fields like this:
- reply_1 = observation
- reply_2 = angle
- quote = quote-tweet draft with a stronger frame
- new_post = original 1710-style post seed inspired by the source idea

Hard rules:
- Write in English
- English only, using Latin characters only
- No hashtags
- No emojis
- No praise of the author
- No flattery
- No invented quotes
- No quotation marks around the whole output
- No fake attribution
- Do not mention the author's handle unless necessary
- Do not write a generic agreement
- Do not simply paraphrase the post
- Extract the latent pattern, frame, tension, aesthetic signal, strategic implication or cultural meaning
- Stay specific to the source post
- Prefer sharp observations over generic abstraction
- Prefer usable angles over summaries
- The output should feel like material Manuel could reuse later in his own voice

Very important negative rules:
- Do not sound like a marketing strategist
- Do not sound like a brand consultant
- Do not sound like ad copy
- Do not sound like promo copy
- Do not sound like a product caption
- Do not sound like an event announcement
- Do not sound like an Instagram caption
- Do not sound like a school essay
- Do not sound like an art-school caption
- Do not sound like a brand deck
- Do not translate cultural signal into generic business advice
- Do not turn style, music, fashion or taste into startup language
- Do not turn sparse or coded posts into corporate analysis
- Do not write phrases like "now available", "don't miss", "stay tuned", "premium materials", "perfect for the season", "limited edition launch", "live updates", "tickets to", "exclusive music", "customer satisfaction", "brand exposure"
- Do not use phrases like "the interplay of", "the tension between", "explore the", "adds depth", "fleeting beauty", "statement piece", "cutting-edge", "innovation", "synergy"
- Do not use verbs or structures like "highlight", "explore", "capture the essence", "use urgency", "drive awareness", "challenge norms", "position as", "frame as", "redefine"
- Do not summarize the source in polished neutral language
- Avoid clean but empty phrasing
- If the output sounds like a museum caption, marketing slide or design-school summary, it is wrong
- Do not output Chinese, Cyrillic, Japanese or mixed-script text
- Do not invent philosopher, founder, artist or celebrity attributions

Preferred mode:
- Preserve the texture of the source when relevant
- Prefer curatorial reading over promotional rewrite
- Prefer editorial framing over explanation
- Prefer signal, taste, positioning and pattern recognition
- If the source is sparse, coded, aesthetic or scene-based, respond with taste and framing, not corporate analysis
- If the tweet is fashion/music/culture coded, preserve the signal without sounding corny
- If the tweet is AI/software/markets, identify where value, leverage or taste is shifting
- If the tweet is art/institutions, identify the frame, display logic or meaning structure
- If the tweet is digital culture/interface, identify the hidden model, archive logic or orientation problem

{minimal_mode_rules}

Bad outputs to avoid:
- generic agreement
- generic praise
- vague motivational writing
- empty abstractions
- summary without angle
- promo language
- consultant language
- ad language
- fake quotes
- fake attribution
- mixed alphabets

Length guidance:
- reply_1 / observation: 8 to 18 words
- reply_2 / angle: 12 to 28 words
- quote: 8 to 24 words
- new_post: 1 to 4 short lines max

Effective subtopic:
{effective_subtopic}

Topic-specific guidance:
{topic_style}

General examples of the kind of writing wanted:

Good observation:
"The interesting part is the frame behind the statement."

Good observation:
"This reads more like a signal than a take."

Good angle:
"The post matters less as an opinion than as evidence of a changing taste structure."

Good quote:
"The signal gets interesting once the frame becomes legible."

Good post seed:
"A lot of cultural signal arrives
before people have language for it."

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
- minimal_mode: {minimal_mode}

Source post:
\"\"\"{post.text}\"\"\"
""".strip()


def build_prompt(post: ScoredPost, mode: str = "reply") -> str:
    if mode == "inspiration":
        return build_inspiration_prompt(post)
    return build_reply_prompt(post)


def build_retry_prompt(
    post: ScoredPost, field_name: str, bad_text: str, mode: str = "reply"
) -> str:
    minimal_mode = mode == "inspiration" and should_force_minimal_inspiration(post)

    if mode == "inspiration":
        field_guidance = {
            "reply_1": "Rewrite it as a sharper observation.",
            "reply_2": "Rewrite it as a stronger angle Manuel could reuse later.",
            "quote": "Rewrite it as a quote-tweet draft with a stronger frame.",
            "new_post": "Rewrite it as an original 1710-style post seed.",
        }
        extra_rules = """
- Do not sound promotional
- Do not sound like ad copy
- Do not sound like brand strategy language
- Do not use product-launch wording
- Do not use mixed alphabets or non-Latin scripts
- Prefer editorial framing, cultural reading, taste or positioning
- Preserve signal without turning it into consultant language
- Do not sound like a school essay
- Do not sound like a polished neutral summary
- Avoid phrases like "the interplay of", "the tension between", "explore the", "adds depth", "innovation", "synergy"
- Avoid verbs like "highlight", "capture the essence", "drive awareness", "challenge norms", "position as", "frame as"
""".strip()

        if minimal_mode:
            extra_rules += """
- Minimal mode is ON
- Keep the rewrite shorter and drier
- Do not inflate the source
- One clean frame is enough
- If the source is promo-heavy, extract the aura, ritual or signal, not the announcement
""".strip()
    else:
        field_guidance = {
            "reply_1": "Rewrite it as a concise natural reply.",
            "reply_2": "Rewrite it as a grounded reflective reply.",
            "quote": "Rewrite it as a quote-tweet draft.",
            "new_post": "Rewrite it as an original post inspired by the tweet.",
        }
        extra_rules = ""

    return f"""
Rewrite only one X draft field.

Field:
{field_name}

Field intent:
{field_guidance.get(field_name, "Rewrite it well.")}

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
- Keep it concise, sharp and grounded
- Add a real angle instead of paraphrasing
{extra_rules}
""".strip()


def regenerate_field(
    post: ScoredPost, field_name: str, bad_text: str, mode: str = "reply"
) -> str:
    prompt = build_retry_prompt(post, field_name, bad_text, mode=mode)

    try:
        result = generate_text(prompt)
        return clean_text(result)
    except Exception as e:
        print(
            f"⚠️ Error regenerando {field_name} para @{clean_handle(post.handle)}: {e}"
        )
        return ""


def repair_drafts(post: ScoredPost, drafts: dict, mode: str = "reply") -> dict:
    repaired = drafts.copy()

    for field_name, value in drafts.items():
        if is_bad_output(value, post.text, mode=mode):
            retry_value = regenerate_field(post, field_name, value, mode=mode)

            if retry_value and not is_bad_output(retry_value, post.text, mode=mode):
                print(
                    f"↻ Campo reparado para @{clean_handle(post.handle)}: {field_name}"
                )
                repaired[field_name] = retry_value
            else:
                print(
                    f"↳ Fallback por campo para @{clean_handle(post.handle)}: {field_name}"
                )
                repaired[field_name] = fallback_field(post, field_name, mode=mode)

    return repaired


def generate_drafts(post: ScoredPost, mode: str = "reply") -> dict:
    prompt = build_prompt(post, mode=mode)

    try:
        result = generate_json(prompt)

        drafts = {
            "reply_1": clean_text(result.get("reply_1", "")),
            "reply_2": clean_text(result.get("reply_2", "")),
            "quote": clean_text(result.get("quote", "")),
            "new_post": clean_text(result.get("new_post", "")),
        }

        return repair_drafts(post, drafts, mode=mode)

    except Exception as e:
        print(
            f"⚠️ Error generando drafts con Ollama para @{clean_handle(post.handle)}: {e}"
        )
        return {
            "reply_1": fallback_field(post, "reply_1", mode=mode),
            "reply_2": fallback_field(post, "reply_2", mode=mode),
            "quote": fallback_field(post, "quote", mode=mode),
            "new_post": fallback_field(post, "new_post", mode=mode),
        }


def get_skip_reason(post: ScoredPost, mode: str = "reply"):
    text = (post.text or "").strip()

    if not text:
        return "sin texto"

    if mode == "reply":
        if post.minutes_since_posted is not None and post.minutes_since_posted > 10080:
            return f"demasiado viejo ({post.minutes_since_posted} min)"

    if looks_like_low_signal_post(text):
        return "post de baja señal"

    if not has_enough_text_substance(text):
        return "sin suficiente sustancia"

    return None
