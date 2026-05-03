from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.api.schemas import ChatRequest, ChatResponse, SessionResponse, SessionStateResponse
from app.config import settings
from app.conversation.service import ConversationService
from app.runtime import ensure_runtime_ready

ensure_runtime_ready(logs_dir=Path(settings.log_file).parent)
_service = ConversationService.for_tests(settings.sessions_dir)
app = FastAPI(title="Netflix Recommendation Chat API")


@app.post("/sessions", response_model=SessionResponse)
def create_session() -> SessionResponse:
    session = _service.start_session()
    return SessionResponse(session_id=session.session_id, state=session.state)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        response = _service.handle_message(request.session_id, request.message)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="session_not_found") from exc
    return ChatResponse.model_validate(response.model_dump())


@app.get("/sessions/{session_id}", response_model=SessionStateResponse)
def get_session(session_id: str) -> SessionStateResponse:
    try:
        session = _service.load_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="session_not_found") from exc
    return SessionStateResponse.model_validate(session.model_dump())


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    _service.store.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}
