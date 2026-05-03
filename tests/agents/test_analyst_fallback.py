from app.orchestration.pipeline import build_fallback_intent


def test_build_fallback_intent_returns_minimal_intent_when_analyst_fails():
    intent = build_fallback_intent("interstellar")

    assert intent.query == "interstellar"
    assert intent.content_type is None
    assert intent.hard_constraints == {}
    assert intent.genre_hypotheses == []
    assert intent.language == "en"
    assert "Analyst failed" in intent.explanation


def test_build_fallback_intent_detects_russian_language():
    intent = build_fallback_intent("хочу фильм про космос")
    assert intent.language == "ru"
