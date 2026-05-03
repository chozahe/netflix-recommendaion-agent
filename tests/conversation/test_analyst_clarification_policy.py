from app.orchestration.pipeline import run_analyst


def test_run_analyst_does_not_short_circuit_rich_query_to_local_clarification(monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.pipeline.build_analyst_agent",
        lambda: object(),
    )
    monkeypatch.setattr("app.orchestration.pipeline.Task", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "app.orchestration.pipeline.Crew",
        lambda *args, **kwargs: type(
            "FakeCrew",
            (),
            {
                "kickoff": lambda self: '{"query":"посоветуй сериал с вайбом 80-х и Вайноной Райдер","content_type":"TV Show","hard_constraints":{},"soft_preferences":{},"topic_hypotheses":[],"genre_hypotheses":[],"mood_hypotheses":[],"language":"ru","explanation":"rich query","needs_clarification":false,"clarification_question":null,"missing_slots":[],"confidence":0.8,"external_signals":["era:1980s","actor:winona_ryder"]}'
            },
        )(),
    )

    intent = run_analyst("посоветуй сериал с вайбом 80-х и Вайноной Райдер")

    assert intent.needs_clarification is False
    assert "actor:winona_ryder" in intent.external_signals


def test_run_analyst_does_not_short_circuit_short_query_to_local_clarification(monkeypatch):
    monkeypatch.setattr(
        "app.orchestration.pipeline.build_analyst_agent",
        lambda: object(),
    )
    monkeypatch.setattr("app.orchestration.pipeline.Task", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        "app.orchestration.pipeline.Crew",
        lambda *args, **kwargs: type(
            "FakeCrew",
            (),
            {
                "kickoff": lambda self: '{"query":"посоветуй","content_type":null,"hard_constraints":{},"soft_preferences":{},"topic_hypotheses":[],"genre_hypotheses":[],"mood_hypotheses":[],"language":"ru","explanation":"need clarification","needs_clarification":true,"clarification_question":"Что именно вам хочется посмотреть?","missing_slots":["content_type"],"confidence":0.2,"external_signals":[]}'
            },
        )(),
    )

    intent = run_analyst("посоветуй")

    assert intent.needs_clarification is True
    assert intent.clarification_question == "Что именно вам хочется посмотреть?"
