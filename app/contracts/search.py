from pydantic import BaseModel, Field


class Candidate(BaseModel):
    title: str
    type: str
    release_year: int
    country: str
    rating: str | None = None
    duration: str | None = None
    listed_in: str = ""
    description: str = ""
    cast: str = ""
    match_features: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    status: str
    selected: list[Candidate]
    discarded: list[Candidate]
    explanation: str
