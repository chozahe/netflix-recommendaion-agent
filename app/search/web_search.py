from __future__ import annotations

from typing import Any

from app.config import settings

try:  # pragma: no cover - import path depends on runtime environment
    from duckduckgo_search import DDGS
except ImportError:  # pragma: no cover - graceful fallback if dependency missing
    DDGS = None


def _normalize_text(value: str) -> str:
    return value.lower().replace("_", " ").replace("-", " ")


def _match_signal(signal: str, haystack: str) -> bool:
    if signal.startswith("actor:"):
        actor_name = _normalize_text(signal.split(":", 1)[1])
        return actor_name in haystack
    if signal.startswith("era:"):
        era_value = signal.split(":", 1)[1].lower()
        if era_value == "1980s":
            return any(marker in haystack for marker in ["1980s", "1980", "80s", "80's"])
        return era_value in haystack
    if signal.startswith("vibe:"):
        vibe_value = _normalize_text(signal.split(":", 1)[1])
        return vibe_value in haystack
    return False


def _score_result(title: str, snippets: list[dict[str, Any]], external_signals: list[str]) -> dict[str, Any]:
    matched_signals: list[str] = []
    evidence: list[str] = []
    for snippet in snippets:
        snippet_text = _normalize_text(
            f"{snippet.get('title', '')} {snippet.get('body', '')}"
        )
        for signal in external_signals:
            if signal not in matched_signals and _match_signal(signal, snippet_text):
                matched_signals.append(signal)
                evidence.append(snippet.get("href") or snippet.get("title") or title)

    return {
        "title": title,
        "summary": snippets[0].get("body") if snippets else None,
        "matched_external_signals": matched_signals,
        "confidence_boost": len(matched_signals),
        "evidence": evidence,
    }


def search_web(query: str, timeout_seconds: int, max_results: int = 5) -> list[dict[str, Any]]:
    if settings.web_enrichment_provider != "duckduckgo" or DDGS is None:
        return []

    try:
        with DDGS(timeout=timeout_seconds) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

    normalized: list[dict[str, Any]] = []
    for item in results:
        normalized.append(
            {
                "title": item.get("title", ""),
                "body": item.get("body", "") or item.get("snippet", ""),
                "href": item.get("href", "") or item.get("url", ""),
            }
        )
    return normalized


def enrich_titles(
    titles: list[str],
    timeout_seconds: int,
    external_signals: list[str] | None = None,
) -> list[dict[str, Any]]:
    signals = list(external_signals or [])
    enriched: list[dict[str, Any]] = []
    for title in titles:
        query_suffix = " ".join(signals)
        query = f"{title} {query_suffix}".strip()
        snippets = search_web(
            query,
            timeout_seconds=timeout_seconds,
            max_results=settings.web_enrichment_search_results,
        )
        enriched.append(_score_result(title, snippets, signals))
    return enriched
