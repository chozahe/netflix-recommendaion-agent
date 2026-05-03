from app.conversation.clarification import needs_clarification



def test_vague_query_requires_clarification():
    result = needs_clarification(query="хочу что-нибудь мрачное")
    assert result is True
