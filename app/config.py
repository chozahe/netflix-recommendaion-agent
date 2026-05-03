import os

from dotenv import load_dotenv
from pydantic import BaseModel


load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)

    if value is None:
        return default

    return float(value)


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)


class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv(
        "OPENAI_BASE_URL",
        "https://opencode.ai/zen/go/v1",
    )

    analyst_model: str = os.getenv("ANALYST_MODEL", "qwen3.5-plus")
    search_model: str = os.getenv("SEARCH_MODEL", "deepseek-v4-pro")
    finalizer_model: str = os.getenv("FINALIZER_MODEL", "deepseek-v4-flash")

    analyst_temperature: float = env_float("ANALYST_TEMPERATURE", 0.1)
    search_temperature: float = env_float("SEARCH_TEMPERATURE", 0.0)
    finalizer_temperature: float = env_float("FINALIZER_TEMPERATURE", 0.4)

    llm_timeout_seconds: int = env_int("LLM_TIMEOUT_SECONDS", 45)
    analyst_max_iter: int = env_int("ANALYST_MAX_ITER", 2)
    searcher_max_iter: int = env_int("SEARCHER_MAX_ITER", 3)
    finalizer_max_iter: int = env_int("FINALIZER_MAX_ITER", 2)

    agents_verbose: bool = env_bool("AGENTS_VERBOSE", True)

    netflix_csv_path: str = os.getenv("NETFLIX_CSV_PATH", "data/netflix_titles.csv")
    sessions_dir: str = os.getenv("SESSIONS_DIR", "memory/sessions")

    metrics_port: int = env_int("METRICS_PORT", 8001)
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = env_int("API_PORT", 8000)
    web_enrichment_enabled: bool = env_bool("WEB_ENRICHMENT_ENABLED", True)
    web_enrichment_provider: str = os.getenv("WEB_ENRICHMENT_PROVIDER", "duckduckgo")
    web_enrichment_max_titles: int = env_int("WEB_ENRICHMENT_MAX_TITLES", 3)
    web_enrichment_search_results: int = env_int("WEB_ENRICHMENT_SEARCH_RESULTS", 5)
    web_enrichment_timeout_seconds: int = env_int("WEB_ENRICHMENT_TIMEOUT_SECONDS", 5)
    log_file: str = os.getenv("LOG_FILE", "logs/app.log")


settings = Settings()
