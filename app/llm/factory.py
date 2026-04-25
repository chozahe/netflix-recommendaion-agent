from langchain_openai import ChatOpenAI

from app.config import settings


def create_llm(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=model,
        temperature=temperature,
    )


def create_analyst_llm() -> ChatOpenAI:
    return create_llm(
        model=settings.analyst_model,
        temperature=settings.analyst_temperature,
    )


def create_search_llm() -> ChatOpenAI:
    return create_llm(
        model=settings.search_model,
        temperature=settings.search_temperature,
    )


def create_finalizer_llm() -> ChatOpenAI:
    return create_llm(
        model=settings.finalizer_model,
        temperature=settings.finalizer_temperature,
    )
