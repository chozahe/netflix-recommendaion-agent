from pydantic import BaseModel, Field


class FeedbackSignal(BaseModel):
    kind: str
    value: str | None = None
    values: list[str] = Field(default_factory=list)
    rejected_titles: list[str] = Field(default_factory=list)
    requires_refinement: bool = False
