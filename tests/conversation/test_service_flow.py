from app.conversation.service import ConversationService



def test_service_returns_clarification_for_vague_query(tmp_path):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()
    response = service.handle_message(session.session_id, "хочу что-нибудь мрачное")
    assert response.type == "clarification"
    assert response.state == "awaiting_clarification"
