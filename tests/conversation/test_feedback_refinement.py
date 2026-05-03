from app.conversation.service import ConversationService



def test_negative_feedback_triggers_refined_recommendations(tmp_path):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()
    service.seed_recommendations(session.session_id, ["Old Title"])
    response = service.handle_message(session.session_id, "это отстой, слишком старое")
    assert response.type in {"clarification", "refined_recommendations"}
