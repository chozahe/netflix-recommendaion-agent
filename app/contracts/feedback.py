from pydantic import BaseModel, Field


class FeedbackSignal(BaseModel):
    kind: str
    value: str | None = None
    rejected_titles: list[str] = Field(default_factory=list)
