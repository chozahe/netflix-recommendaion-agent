from pydantic import BaseModel, Field

from app.memory.models import StoredRecommendation


class ConversationResponse(BaseModel):
    type: str
    session_id: str
    message: str
    recommendations: list[StoredRecommendation] = Field(default_factory=list)
    state: str
