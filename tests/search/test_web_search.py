from app.search.web_search import enrich_titles


def test_enrich_titles_scores_actor_and_era_matches(monkeypatch):
    monkeypatch.setattr(
        "app.search.web_search.search_web",
        lambda query, timeout_seconds, max_results=5: [
            {
                "title": "Stranger Things - Wikipedia",
                "body": "Set in the 1980s and starring Winona Ryder.",
                "href": "https://example.com/stranger-things",
            }
        ],
    )

    enriched = enrich_titles(
        ["Stranger Things"],
        timeout_seconds=5,
        external_signals=["era:1980s", "actor:winona_ryder"],
    )

    assert enriched[0]["title"] == "Stranger Things"
    assert "era:1980s" in enriched[0]["matched_external_signals"]
    assert "actor:winona_ryder" in enriched[0]["matched_external_signals"]
    assert enriched[0]["confidence_boost"] >= 2
