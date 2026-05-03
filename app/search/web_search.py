from typing import Any


def enrich_titles(titles: list[str], timeout_seconds: int) -> list[dict[str, Any]]:
    return [{"title": title, "summary": None} for title in titles]
