from typing import Any


def enrich_titles(
    titles: list[str],
    timeout_seconds: int,
    external_signals: list[str] | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "title": title,
            "summary": None,
            "matched_external_signals": list(external_signals or []),
            "confidence_boost": 0,
        }
        for title in titles
    ]
