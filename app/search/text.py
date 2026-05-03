import re


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize_query(text: str) -> list[str]:
    return [token for token in normalize_text(text).split() if len(token) > 1]
