from pathlib import Path

from app.chat import run_chat
from app.config import settings
from app.monitoring import get_logger, setup_logging, setup_metrics
from app.runtime import ensure_runtime_ready

_logger = get_logger(__name__)


def main() -> None:
    ensure_runtime_ready(logs_dir=Path(settings.log_file).parent)
    setup_logging(settings.log_file)
    setup_metrics(settings.metrics_port)
    _logger.info("chat_cli_started", metrics_port=settings.metrics_port)
    run_chat()


if __name__ == "__main__":
    main()
