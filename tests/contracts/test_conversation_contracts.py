from app.contracts.conversation import ConversationResponse
from app.memory.models import SessionMemory


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
