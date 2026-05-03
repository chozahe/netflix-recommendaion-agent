from app.llm.providers import create_provider_llm


def test_create_provider_llm_sets_timeout_for_openai_backend(monkeypatch):
    captured = {}

    class _DummyChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("app.llm.providers.ChatOpenAI", _DummyChatOpenAI)

    create_provider_llm(model="openai/qwen3.5-plus", temperature=0.1)

    assert captured["timeout"] == 45
