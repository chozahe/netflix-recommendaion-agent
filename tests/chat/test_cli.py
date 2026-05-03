from app.chat.cli import format_agent_reply



def test_format_agent_reply_handles_clarification():
    rendered = format_agent_reply({"message": "Movie or TV show?"})
    assert "Movie or TV show?" in rendered


def test_format_agent_reply_includes_poster_url_when_no_inline_renderer(monkeypatch):
    monkeypatch.setattr("app.chat.cli._try_inline_image", lambda url: False)
    rendered = format_agent_reply({
        "message": "Here are your picks",
        "recommendations": [
            {"title": "Inception", "poster_url": "https://example.com/inception.jpg"},
        ],
    })
    assert "Here are your picks" in rendered
    assert "https://example.com/inception.jpg" in rendered


def test_format_agent_reply_skips_missing_poster_url():
    rendered = format_agent_reply({
        "message": "Here are your picks",
        "recommendations": [
            {"title": "Inception", "poster_url": None},
        ],
    })
    assert "Here are your picks" in rendered
    assert "Inception" not in rendered  # we don't mention title unless there's a poster


def test_format_agent_reply_does_not_crash_when_inline_renderer_fails(monkeypatch):
    def raise_exception(url):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.chat.cli._try_inline_image", raise_exception)
    rendered = format_agent_reply({
        "message": "Here are your picks",
        "recommendations": [
            {"title": "Inception", "poster_url": "https://example.com/inception.jpg"},
        ],
    })
    assert "Here are your picks" in rendered
    assert "https://example.com/inception.jpg" in rendered
