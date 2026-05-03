from app.orchestration.pipeline import build_fallback_intent


def test_build_fallback_intent_uses_preference_extractor_payload(monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.pipeline.PreferenceExtractorTool._run",
        lambda self, query: '{"content_type": "Movie", "genres": ["Sci-Fi & Fantasy"], "year_from": 2010, "year_to": 2020, "country": "United States", "rating_filter": ["PG-13"], "reasoning": "fallback"}',
    )

    intent = build_fallback_intent("interstellar")

    assert intent.query == "interstellar"
    assert intent.content_type == "Movie"
    assert intent.hard_constraints["year_from"] == 2010
    assert intent.hard_constraints["country"] == "United States"
    assert intent.genre_hypotheses == ["Sci-Fi & Fantasy"]
