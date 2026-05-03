from app.contracts.analyst import AnalystIntent
from app.conversation.service import ConversationService


def test_anything_is_fine_stops_further_clarification(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    monkeypatch.setattr(
        "app.conversation.service.run_analyst",
        lambda query: AnalystIntent(
            query=query,
            language="ru",
            explanation="need clarification",
            needs_clarification=True,
            clarification_question="Какой вайб?",
            missing_slots=["vibe"],
            confidence=0.4,
        ),
    )
    monkeypatch.setattr("app.conversation.service.run_searcher", lambda intent, last_tool_result=None: '{"selected": []}')
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: "done")

    service.handle_message(session.session_id, "хочу детективный сериал на вечер")
    response = service.handle_message(session.session_id, "да любое сойдет")
    updated = service.load_session(session.session_id)

    assert response.type == "recommendations"
    assert updated.clarification_count == 1


def test_clarification_is_capped_at_two_turns(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    monkeypatch.setattr(
        "app.conversation.service.run_analyst",
        lambda query: AnalystIntent(
            query=query,
            language="ru",
            explanation="need clarification",
            needs_clarification=True,
            clarification_question="Уточните запрос?",
            missing_slots=["vibe"],
            confidence=0.2,
        ),
    )
    monkeypatch.setattr("app.conversation.service.run_searcher", lambda intent, last_tool_result=None: '{"selected": []}')
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: "done")

    first = service.handle_message(session.session_id, "хочу что-нибудь")
    second = service.handle_message(session.session_id, "не знаю")
    third = service.handle_message(session.session_id, "ну еще не знаю")
    updated = service.load_session(session.session_id)

    assert first.type == "clarification"
    assert second.type == "clarification"
    assert third.type == "recommendations"
    assert updated.clarification_count == 2
