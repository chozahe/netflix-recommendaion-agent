from app.contracts.analyst import AnalystIntent
from app.conversation.service import ConversationService
from app.memory.models import StoredRecommendation



def test_clarification_answer_merges_with_existing_intent(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    analyst_calls: list[str] = []

    def fake_run_analyst(query: str) -> AnalystIntent:
        analyst_calls.append(query)
        if query == "хочу что-нибудь мрачное":
            return AnalystIntent(
                query=query,
                language="ru",
                explanation="need clarification",
                needs_clarification=True,
                clarification_question="Это фильм или сериал?",
                missing_slots=["content_type"],
            )
        raise AssertionError(f"unexpected analyst call: {query}")

    def fake_run_searcher(intent: AnalystIntent, last_tool_result: dict | None = None) -> str:
        assert intent.query == "хочу что-нибудь мрачное фильм"
        assert intent.content_type == "Movie"
        return '{"selected": [{"title": "Dark Movie", "reason": "match"}]}'

    monkeypatch.setattr("app.conversation.service.run_analyst", fake_run_analyst)
    monkeypatch.setattr("app.conversation.service.run_searcher", fake_run_searcher)
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: "final")

    first = service.handle_message(session.session_id, "хочу что-нибудь мрачное")
    second = service.handle_message(session.session_id, "фильм")

    assert first.type == "clarification"
    assert second.type == "recommendations"
    assert analyst_calls == ["хочу что-нибудь мрачное"]



def test_negative_feedback_reruns_search_and_returns_structured_recommendations(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()
    service.seed_recommendations(session.session_id, ["Old Title"])

    session_memory = service.load_session(session.session_id)
    session_memory.current_intent = AnalystIntent(
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
    service.store.save_session(session_memory)

    def fake_run_searcher(intent: AnalystIntent, last_tool_result: dict | None = None) -> str:
        assert intent.hard_constraints["year_from"] == 2018
        return '{"selected": [{"title": "New Title", "reason": "newer"}]}'

    monkeypatch.setattr("app.conversation.service.run_searcher", fake_run_searcher)
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: "refined")

    response = service.handle_message(session.session_id, "это отстой, слишком старое")

    assert response.type == "refined_recommendations"
    assert response.recommendations == [StoredRecommendation(title="New Title", reason="newer")]
    updated = service.load_session(session.session_id)
    assert "Old Title" in updated.rejected_titles
    assert updated.last_recommendations == [StoredRecommendation(title="New Title", reason="newer")]
