from app.contracts.conversation import ConversationResponse
from app.memory.models import SessionMemory, StoredRecommendation


def test_conversation_response_supports_clarification_and_recommendations():
    response = ConversationResponse(
        type="clarification",
        session_id="s1",
        message="Movie or TV show?",
        recommendations=[],
        state="awaiting_clarification",
    )
    assert response.type == "clarification"


def test_session_memory_tracks_dialog_state():
    memory = SessionMemory(session_id="s1")
    assert memory.state == "idle"
    assert memory.shown_titles == []


def test_stored_recommendation_accepts_poster_url():
    rec = StoredRecommendation(title="Inception", reason="Great sci-fi", poster_url="https://example.com/poster.jpg")
    assert rec.poster_url == "https://example.com/poster.jpg"


def test_stored_recommendation_defaults_poster_url_to_none():
    rec = StoredRecommendation(title="Inception", reason="Great sci-fi")
    assert rec.poster_url is None


def test_conversation_response_serializes_recommendations_with_poster_url():
    response = ConversationResponse(
        type="recommendations",
        session_id="s1",
        message="Here are some picks",
        recommendations=[
            StoredRecommendation(title="Inception", poster_url="https://example.com/inception.jpg"),
            StoredRecommendation(title="Unknown", poster_url=None),
        ],
        state="recommended",
    )
    data = response.model_dump()
    assert data["recommendations"][0]["poster_url"] == "https://example.com/inception.jpg"
    assert data["recommendations"][1]["poster_url"] is None
