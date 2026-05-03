from pathlib import Path

from app.runtime.bootstrap import ensure_runtime_ready


def test_ensure_runtime_ready_creates_runtime_directories(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    chroma_dir = tmp_path / "chroma_db"

    ensure_runtime_ready(logs_dir=logs_dir, chroma_dir=chroma_dir)

    assert logs_dir.exists()
    assert chroma_dir.exists()
