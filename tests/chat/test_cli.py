from app.chat.cli import format_agent_reply



def test_format_agent_reply_handles_clarification():
    rendered = format_agent_reply({"message": "Movie or TV show?"})
    assert "Movie or TV show?" in rendered
