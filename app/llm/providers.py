from __future__ import annotations

import httpx
from langchain_core.language_models.llms import LLM
from langchain_openai import ChatOpenAI

from app.config import settings

ANTHROPIC_STYLE_MODELS = {
    "minimax-m2.5",
    "minimax-m2.7",
}

_ANTHROPIC_API_URL = "https://opencode.ai/zen/go/v1/messages"


def normalize_model_name(model: str) -> str:
    return model.replace("openai/", "").replace("anthropic/", "").replace("opencode-go/", "")


def classify_model_backend(model: str) -> str:
    clean = normalize_model_name(model)
    return "anthropic" if clean in ANTHROPIC_STYLE_MODELS else "openai"


class AnthropicMessagesLLM(LLM):
    model: str = ""
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "anthropic_messages"

    def _call(self, prompt: str, stop=None, **kwargs) -> str:
        body = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.openai_api_key,
            "anthropic-version": "2023-06-01",
        }
        response = httpx.post(_ANTHROPIC_API_URL, json=body, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()
        texts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
        return "\n".join(texts)


def create_provider_llm(model: str, temperature: float):
    clean = normalize_model_name(model)
    backend = classify_model_backend(model)
    if backend == "anthropic":
        return AnthropicMessagesLLM(model=clean, temperature=temperature)
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=model,
        temperature=temperature,
    )
