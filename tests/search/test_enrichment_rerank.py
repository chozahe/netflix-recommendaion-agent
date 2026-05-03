from app.contracts.analyst import AnalystIntent
from app.orchestration.pipeline import maybe_enrich_search_output


def test_enrichment_reranks_candidates_using_external_signals(monkeypatch):
    intent = AnalystIntent(
        query="сериал с вайбом 80-х и Вайноной Райдер",
        content_type="TV Show",
        external_signals=["era:1980s", "actor:winona_ryder"],
    )
    search_output = '{"selected":[{"title":"Stranger Things","reason":"cast match"},{"title":"Some Other Show","reason":"partial match"}]}'

    monkeypatch.setattr(
        "app.orchestration.pipeline.enrich_shortlisted_titles",
        lambda query, titles, external_signals=None: [
            {"title": "Stranger Things", "matched_external_signals": ["era:1980s", "actor:winona_ryder"], "confidence_boost": 2},
            {"title": "Some Other Show", "matched_external_signals": [], "confidence_boost": 0},
        ],
    )

    enriched = maybe_enrich_search_output(intent, search_output)
    assert enriched["selected"][0]["title"] == "Stranger Things"
    assert enriched["enrichment_used"] is True


def test_enrichment_marks_used_only_when_real_signal_match_exists(monkeypatch):
    intent = AnalystIntent(
        query="сериал с вайбом 80-х и Вайноной Райдер",
        content_type="TV Show",
        external_signals=["era:1980s", "actor:winona_ryder"],
    )
    search_output = '{"selected":[{"title":"Stranger Things","reason":"cast match"}]}'

    monkeypatch.setattr(
        "app.orchestration.pipeline.enrich_shortlisted_titles",
        lambda query, titles, external_signals=None: [
            {"title": "Stranger Things", "matched_external_signals": [], "confidence_boost": 0}
        ],
    )

    enriched = maybe_enrich_search_output(intent, search_output)
    assert enriched["enrichment_used"] is False
