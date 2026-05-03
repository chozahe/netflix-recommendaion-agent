from app.contracts.analyst import AnalystIntent
from app.conversation.service import ConversationService


def test_feedback_updates_rejected_preference_memory(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()
    service.seed_recommendations(session.session_id, ["Old Title"])
    memory = service.load_session(session.session_id)
    memory.current_intent = AnalystIntent(
        query="хочу фантастику",
        content_type="Movie",
        hard_constraints={},
        soft_preferences={},
        topic_hypotheses=[],
        genre_hypotheses=[],
        mood_hypotheses=[],
        language="ru",
        explanation="base intent",
    )
    memory.rejected_soft_preferences = {}
    service.store.save_session(memory)

    monkeypatch.setattr("app.conversation.service.run_searcher", lambda intent, last_tool_result=None: '{"selected": []}')
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: {"message": "refined", "posters": []})

    service.handle_message(session.session_id, "слишком старое и слишком медленное")
    updated = service.load_session(session.session_id)

    assert updated.rejected_soft_preferences["age"] == ["old"]
    assert updated.rejected_soft_preferences["pace"] == ["slow"]


def test_recommendation_flow_persists_external_signal_history_and_accepted_preferences(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    monkeypatch.setattr(
        "app.conversation.service.run_analyst",
        lambda query: AnalystIntent(
            query=query,
            content_type="TV Show",
            soft_preferences={"vibe": ["mysterious"]},
            language="ru",
            explanation="rich query",
            confidence=0.8,
            external_signals=["era:1980s", "actor:winona_ryder"],
        ),
    )
    monkeypatch.setattr("app.conversation.service.run_searcher", lambda intent, last_tool_result=None: '{"selected": []}')
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: {"message": "done", "posters": []})

    service.handle_message(session.session_id, "посоветуй сериал с вайбом 80-х и Вайноной Райдер")
    updated = service.load_session(session.session_id)

    assert updated.accepted_soft_preferences["vibe"] == ["mysterious"]
    assert "era:1980s" in updated.external_signal_history
    assert "actor:winona_ryder" in updated.external_signal_history
