import json as json_module

import httpx
from langchain_core.language_models.llms import LLM
from langchain_openai import ChatOpenAI

from app.config import settings

ANTHROPIC_MODEL_IDS = {
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "minimax-m2.5",
    "minimax-m2.7",
}

_ANTHROPIC_API_URL = "https://opencode.ai/zen/go/v1/messages"


class _AnthropicLLM(LLM):
    """Minimal LangChain-compatible wrapper over the Anthropic Messages API."""

    model: str = ""
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "anthropic_messages"

    def _call(self, prompt: str, stop=None, **kwargs) -> str:
        # Build messages array from the string prompt.
        # CrewAI passes the full backstory+task+history as a single string.
        messages = [{"role": "user", "content": prompt}]

        body = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "temperature": self.temperature,
            "messages": messages,
            **kwargs,
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.openai_api_key,
            "anthropic-version": "2023-06-01",
        }

        response = httpx.post(
            _ANTHROPIC_API_URL,
            json=body,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        # Anthropic returns content blocks; extract text
        blocks = data.get("content", [])
        texts = [b["text"] for b in blocks if b.get("type") == "text"]
        return "\n".join(texts)


def create_llm(model: str, temperature: float):
    clean = model.replace("openai/", "").replace("anthropic/", "").replace("opencode-go/", "")

    if clean in ANTHROPIC_MODEL_IDS:
        return _AnthropicLLM(model=clean, temperature=temperature)

    # Keep prefix in model name — CrewAI/LiteLLM needs it for provider routing
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=model,
        temperature=temperature,
    )


def create_analyst_llm():
    return create_llm(model=settings.analyst_model, temperature=settings.analyst_temperature)


def create_search_llm():
    return create_llm(model=settings.search_model, temperature=settings.search_temperature)


def create_finalizer_llm():
    return create_llm(model=settings.finalizer_model, temperature=settings.finalizer_temperature)
