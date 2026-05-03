import sys
from pathlib import Path

from app.config import settings
from app.monitoring import (
    REQUESTS_TOTAL,
    REQUEST_DURATION,
    get_logger,
    setup_logging,
    setup_metrics,
)
from app.orchestration import run_pipeline
from app.runtime import ensure_runtime_ready

_logger = get_logger(__name__)


def main() -> None:
    ensure_runtime_ready(
        logs_dir=Path(settings.log_file).parent,
        chroma_dir=Path(settings.chroma_path),
    )
    setup_logging(settings.log_file)
    setup_metrics(settings.metrics_port)
    _logger.info("system_started", metrics_port=settings.metrics_port)

    if not settings.openai_api_key:
        _logger.error("no_api_key")
        print("ERROR: OPENAI_API_KEY is not set. Create a .env file with your key.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python -m app.main 'Your Netflix query here'")
        print('Example: python -m app.main "хочу фильм про космос"')
        sys.exit(0)

    query = " ".join(sys.argv[1:])
    _logger.info("request_received", query=query)

    try:
        with REQUEST_DURATION.time():
            result = run_pipeline(query)

        REQUESTS_TOTAL.labels(status="success").inc()
        _logger.info("request_completed", query=query)
        print()
        print(result)
    except Exception as exc:
        REQUESTS_TOTAL.labels(status="error").inc()
        _logger.error("request_failed", query=query, error=str(exc))
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
