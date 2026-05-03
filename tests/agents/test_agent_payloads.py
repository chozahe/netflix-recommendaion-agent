from app.contracts.analyst import AnalystIntent
from app.orchestration.pipeline import build_searcher_input


def test_build_searcher_input_passes_only_query_intent_and_last_tool_result():
    intent = AnalystIntent(
        query="что-нибудь мрачное про космос",
        content_type=None,
        hard_constraints={},
        soft_preferences={"topics": ["space"]},
        topic_hypotheses=["space survival"],
        genre_hypotheses=["Sci-Fi & Fantasy"],
        mood_hypotheses=["dark"],
        language="ru",
        explanation="Detected dark space request",
    )

    payload = build_searcher_input(intent=intent, last_tool_result={"candidates": []})

    assert payload["query"] == intent.query
    assert payload["intent"]["topic_hypotheses"] == ["space survival"]
    assert payload["last_tool_result"] == {"candidates": []}
