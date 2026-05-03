from __future__ import annotations

from pydantic import BaseModel, Field


class ConversationResponse(BaseModel):
    type: str
    session_id: str
    message: str
    recommendations: list["StoredRecommendation"] = Field(default_factory=list)
    state: str
