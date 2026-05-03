import re

VAGUE_RU_MARKERS = [
    "что-нибудь",
    "что нибудь",
    "не знаю",
]
CONTENT_HINTS = ["фильм", "сериал", "movie", "show", "tv"]


def detect_missing_slots(query: str) -> list[str]:
    text = query.lower()
    missing: list[str] = []

    if not any(hint in text for hint in CONTENT_HINTS):
        missing.append("content_type")
    return missing



def needs_clarification(query: str) -> bool:
    text = query.lower().strip()
    if any(marker in text for marker in VAGUE_RU_MARKERS):
        return True
    if re.fullmatch(r"[\w\s-]{1,20}", text) and len(text.split()) <= 3 and not any(
        hint in text for hint in CONTENT_HINTS
    ):
        return True
    return False



def build_clarification_question(query: str) -> str:
    missing_slots = detect_missing_slots(query)
    if "content_type" in missing_slots:
        return "Это должен быть фильм или сериал?"
    return "Можете чуть точнее описать, что вам хочется посмотреть?"
