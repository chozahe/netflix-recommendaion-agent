import json

import pytest

from app.conversation.service import ConversationService
from app.memory.models import StoredRecommendation


def test_build_recommendation_response_merges_posters_from_finalizer(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    def fake_run_searcher(intent, last_tool_result=None):
        return json.dumps({
            "selected": [
                {"title": "Inception", "reason": "sci-fi", "type": "Movie", "release_year": 2010},
                {"title": "Interstellar", "reason": "space", "type": "Movie", "release_year": 2014},
            ]
        }, ensure_ascii=False)

    def fake_run_finalizer(message, intent, search_output):
        return {
            "message": "Here are your picks",
            "posters": [
                {"title": "Inception", "poster_url": "https://example.com/inception.jpg"},
                {"title": "Interstellar", "poster_url": None},
            ],
        }

    monkeypatch.setattr("app.conversation.service.run_searcher", fake_run_searcher)
    monkeypatch.setattr("app.conversation.service.run_finalizer", fake_run_finalizer)

    from app.contracts.analyst import AnalystIntent
    intent = AnalystIntent(
        query="sci-fi movies",
        language="en",
        explanation="test",
    )

    response = service._build_recommendation_response(
        session=session,
        intent=intent,
        message="sci-fi movies",
        response_type="recommendations",
    )

    assert response.type == "recommendations"
    assert len(response.recommendations) == 2
    assert response.recommendations[0].title == "Inception"
    assert response.recommendations[0].poster_url == "https://example.com/inception.jpg"
    assert response.recommendations[1].title == "Interstellar"
    assert response.recommendations[1].poster_url is None


def test_poster_lookup_gracefully_handles_invalid_search_output(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    def fake_run_searcher(intent, last_tool_result=None):
        return "not valid json"

    def fake_run_finalizer(message, intent, search_output):
        return {"message": "Here are your picks", "posters": []}

    monkeypatch.setattr("app.conversation.service.run_searcher", fake_run_searcher)
    monkeypatch.setattr("app.conversation.service.run_finalizer", fake_run_finalizer)

    from app.contracts.analyst import AnalystIntent
    intent = AnalystIntent(
        query="movies",
        language="en",
        explanation="test",
    )

    response = service._build_recommendation_response(
        session=session,
        intent=intent,
        message="movies",
        response_type="recommendations",
    )

    assert response.type == "recommendations"
    assert response.recommendations == []


def test_poster_lookup_ignores_posters_for_unknown_titles(tmp_path, monkeypatch):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    def fake_run_searcher(intent, last_tool_result=None):
        return json.dumps({
            "selected": [
                {"title": "Inception", "reason": "sci-fi"},
            ]
        }, ensure_ascii=False)

    def fake_run_finalizer(message, intent, search_output):
        return {
            "message": "Here are your picks",
            "posters": [
                {"title": "Inception", "poster_url": "https://example.com/inception.jpg"},
                {"title": "Unknown Title", "poster_url": "https://example.com/unknown.jpg"},
            ],
        }

    monkeypatch.setattr("app.conversation.service.run_searcher", fake_run_searcher)
    monkeypatch.setattr("app.conversation.service.run_finalizer", fake_run_finalizer)

    from app.contracts.analyst import AnalystIntent
    intent = AnalystIntent(
        query="sci-fi",
        language="en",
        explanation="test",
    )

    response = service._build_recommendation_response(
        session=session,
        intent=intent,
        message="sci-fi",
        response_type="recommendations",
    )

    assert len(response.recommendations) == 1
    assert response.recommendations[0].poster_url == "https://example.com/inception.jpg"
