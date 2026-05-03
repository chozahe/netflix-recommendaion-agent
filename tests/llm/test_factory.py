from app.llm.factory import classify_model_backend


def test_classify_model_backend_supports_openai_compatible_models():
    assert classify_model_backend("qwen3.5-plus") == "openai"


def test_classify_model_backend_supports_anthropic_style_models():
    assert classify_model_backend("deepseek-v4-pro") == "anthropic"
