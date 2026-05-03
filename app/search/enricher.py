from app.config import settings
from app.search.web_search import enrich_titles

VIBE_MARKERS = {"мрач", "атмосфер", "vibe", "moody", "sci-fi", "sci fi", "вайб"}
EXTERNAL_SIGNAL_PREFIXES = ("era:", "actor:", "vibe:")



def should_enrich_results(
    query: str,
    candidate_count: int,
    external_signals: list[str] | None = None,
) -> bool:
    text = query.lower()
    has_vibe_markers = any(marker in text for marker in VIBE_MARKERS)
    has_external_markers = any(
        signal.startswith(EXTERNAL_SIGNAL_PREFIXES) for signal in (external_signals or [])
    )
    return (
        settings.web_enrichment_enabled
        and candidate_count > 0
        and (has_vibe_markers or has_external_markers)
    )



def enrich_shortlisted_titles(
    query: str,
    titles: list[str],
    external_signals: list[str] | None = None,
) -> list[dict]:
    if not should_enrich_results(query, len(titles), external_signals=external_signals):
        return []
    limited_titles = titles[: settings.web_enrichment_max_titles]
    return enrich_titles(
        limited_titles,
        settings.web_enrichment_timeout_seconds,
        external_signals=external_signals,
    )
