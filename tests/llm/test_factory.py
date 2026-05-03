from app.llm.factory import classify_model_backend


def test_classify_model_backend_supports_openai_compatible_models():
    assert classify_model_backend("qwen3.5-plus") == "openai"
    assert classify_model_backend("deepseek-v4-pro") == "openai"
    assert classify_model_backend("deepseek-v4-flash") == "openai"


def test_classify_model_backend_supports_anthropic_style_models():
    assert classify_model_backend("minimax-m2.5") == "anthropic"
