from pathlib import Path


def ensure_runtime_ready(*, logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
