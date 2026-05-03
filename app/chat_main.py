from pathlib import Path

from app.chat import run_chat
from app.config import settings
from app.monitoring import setup_logging
from app.runtime import ensure_runtime_ready



def main() -> None:
    ensure_runtime_ready(logs_dir=Path(settings.log_file).parent)
    setup_logging(settings.log_file)
    run_chat()


if __name__ == "__main__":
    main()
