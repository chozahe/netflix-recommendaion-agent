import json
from pathlib import Path
from uuid import uuid4

from app.memory.models import SessionMemory


class FileSessionStore:
    def __init__(self, sessions_dir: str | Path):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> SessionMemory:
        session = SessionMemory(session_id=str(uuid4()))
        session.analytics.mark_started()
        self.save_session(session)
        return session

    def load_session(self, session_id: str) -> SessionMemory:
        return SessionMemory.model_validate_json(self._session_path(session_id).read_text())

    def save_session(self, session: SessionMemory) -> SessionMemory:
        self._session_path(session.session_id).write_text(
            session.model_dump_json(indent=2),
        )
        return session

    def delete_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"
