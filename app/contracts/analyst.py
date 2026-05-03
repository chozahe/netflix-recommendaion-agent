from pydantic import BaseModel, Field


class AnalystIntent(BaseModel):
    query: str
    content_type: str | None = None
    hard_constraints: dict = Field(default_factory=dict)
    soft_preferences: dict = Field(default_factory=dict)
    topic_hypotheses: list[str] = Field(default_factory=list)
    genre_hypotheses: list[str] = Field(default_factory=list)
    mood_hypotheses: list[str] = Field(default_factory=list)
    language: str = "ru"
    explanation: str = ""
    needs_clarification: bool = False
    clarification_question: str | None = None
    missing_slots: list[str] = Field(default_factory=list)
