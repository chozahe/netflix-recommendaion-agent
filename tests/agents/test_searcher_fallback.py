from app.contracts.analyst import AnalystIntent
from app.orchestration.pipeline import build_fallback_search_result


def test_build_fallback_search_result_returns_no_results_when_catalog_is_empty(monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.pipeline.NetflixSearchTool._run",
        lambda self, **kwargs: '{"count": 0, "filters_applied": ["mode=title"], "results": []}',
    )

    intent = AnalystIntent(
        query="interstellar",
        content_type=None,
        hard_constraints={"year_from": None, "year_to": None, "country": None, "rating": None},
        soft_preferences={},
        topic_hypotheses=[],
        genre_hypotheses=[],
        mood_hypotheses=[],
        language="en",
        explanation="fallback",
    )

    result = build_fallback_search_result(intent)

    assert result.status == "no_results"
    assert result.selected == []
