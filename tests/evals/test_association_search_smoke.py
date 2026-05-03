from app.contracts.analyst import AnalystIntent
from app.conversation.service import ConversationService
from app.memory.models import StoredRecommendation


def test_association_query_prefers_db_first_then_enrichment(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    monkeypatch.setattr(
        "app.conversation.service.run_analyst",
        lambda query: AnalystIntent(
            query=query,
            content_type="TV Show",
            language="ru",
            explanation="rich association query",
            needs_clarification=False,
            confidence=0.82,
            external_signals=["era:1980s", "actor:winona_ryder", "vibe:mysterious"],
        ),
    )
    monkeypatch.setattr(
        "app.conversation.service.run_searcher",
        lambda intent, last_tool_result=None: '{"selected": [{"title": "Some Other Show", "reason": "partial match"}, {"title": "Stranger Things", "reason": "cast match"}]}',
    )
    monkeypatch.setattr(
        "app.conversation.service.maybe_enrich_search_output",
        lambda intent, search_output: {
            "selected": [
                {
                    "title": "Stranger Things",
                    "reason": "cast match",
                    "matched_external_signals": ["era:1980s", "actor:winona_ryder"],
                    "confidence_boost": 2,
                },
                {
                    "title": "Some Other Show",
                    "reason": "partial match",
                    "matched_external_signals": [],
                    "confidence_boost": 0,
                },
            ],
            "enrichment_used": True,
        },
    )
    monkeypatch.setattr("app.conversation.service.run_finalizer", lambda message, intent, search_output: "ready")

    response = service.handle_message(
        session.session_id,
        "посоветуй сериал с вайбом 80-х и Вайноной Райдер",
    )

    assert response.type == "recommendations"
    assert response.recommendations[0] == StoredRecommendation(title="Stranger Things", reason="cast match")
    updated = service.load_session(session.session_id)
    assert updated.current_intent.external_signals == ["era:1980s", "actor:winona_ryder", "vibe:mysterious"]
