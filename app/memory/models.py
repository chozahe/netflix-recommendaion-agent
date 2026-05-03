from pydantic import BaseModel, Field

from app.contracts.analyst import AnalystIntent
from app.contracts.feedback import FeedbackSignal


class ConversationTurn(BaseModel):
    role: str
    message: str


class StoredRecommendation(BaseModel):
    title: str
    reason: str | None = None
    poster_url: str | None = None


class SessionMemory(BaseModel):
    session_id: str
    state: str = "idle"
    turns: list[ConversationTurn] = Field(default_factory=list)
    shown_titles: list[str] = Field(default_factory=list)
    rejected_titles: list[str] = Field(default_factory=list)
    current_intent: AnalystIntent | None = None
    last_recommendations: list[StoredRecommendation] = Field(default_factory=list)
    feedback_signals: list[FeedbackSignal] = Field(default_factory=list)
    clarification_count: int = 0
    accepted_soft_preferences: dict = Field(default_factory=dict)
    rejected_soft_preferences: dict = Field(default_factory=dict)
    external_signal_history: list[str] = Field(default_factory=list)
