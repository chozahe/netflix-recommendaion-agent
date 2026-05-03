from pydantic import BaseModel

from app.contracts.conversation import ConversationResponse
from app.memory.models import SessionMemory


class ChatRequest(BaseModel):
    session_id: str
    message: str


class SessionResponse(BaseModel):
    session_id: str
    state: str


class SessionStateResponse(SessionMemory):
    pass


class ChatResponse(ConversationResponse):
    pass
