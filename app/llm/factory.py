from app.config import settings
from app.llm.providers import classify_model_backend, create_provider_llm


def create_llm(model: str, temperature: float):
    return create_provider_llm(model=model, temperature=temperature)


def create_analyst_llm():
    return create_llm(model=settings.analyst_model, temperature=settings.analyst_temperature)


def create_search_llm():
    return create_llm(model=settings.search_model, temperature=settings.search_temperature)


def create_finalizer_llm():
    return create_llm(model=settings.finalizer_model, temperature=settings.finalizer_temperature)


__all__ = [
    "classify_model_backend",
    "create_llm",
    "create_analyst_llm",
    "create_search_llm",
    "create_finalizer_llm",
]
