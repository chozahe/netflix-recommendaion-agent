from app.contracts.analyst import AnalystIntent


def test_analyst_intent_accepts_hard_and_soft_constraints():
    intent = AnalystIntent(
        query="что-нибудь мрачное про космос",
        content_type=None,
        hard_constraints={"year_from": None, "year_to": None},
        soft_preferences={"mood": ["dark"], "topics": ["space"]},
        topic_hypotheses=["space survival"],
        genre_hypotheses=["Sci-Fi & Fantasy"],
        mood_hypotheses=["dark"],
        language="ru",
        explanation="Detected space topic and dark mood",
    )

    assert intent.language == "ru"
    assert intent.soft_preferences["topics"] == ["space"]


def test_analyst_intent_supports_confidence_and_external_signals():
    intent = AnalystIntent(
        query="сериал с вайбом 80-х",
        confidence=0.72,
        external_signals=["era:1980s", "vibe:mysterious"],
    )
    assert intent.confidence == 0.72
    assert "era:1980s" in intent.external_signals
