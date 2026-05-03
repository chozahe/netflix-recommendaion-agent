from pydantic import BaseModel


class AnalystIntent(BaseModel):
    query: str
    content_type: str | None = None
    hard_constraints: dict
    soft_preferences: dict
    topic_hypotheses: list[str]
    genre_hypotheses: list[str]
    mood_hypotheses: list[str]
    language: str
    explanation: str
