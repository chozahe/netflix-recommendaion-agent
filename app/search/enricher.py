from app.config import settings
from app.search.web_search import enrich_titles

VIBE_MARKERS = {"мрач", "атмосфер", "vibe", "moody", "sci-fi", "sci fi"}



def should_enrich_results(query: str, candidate_count: int) -> bool:
    text = query.lower()
    return (
        settings.web_enrichment_enabled
        and candidate_count > 0
        and any(marker in text for marker in VIBE_MARKERS)
    )



def enrich_shortlisted_titles(query: str, titles: list[str]) -> list[dict]:
    if not should_enrich_results(query, len(titles)):
        return []
    limited_titles = titles[: settings.web_enrichment_max_titles]
    return enrich_titles(limited_titles, settings.web_enrichment_timeout_seconds)
