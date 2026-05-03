from pydantic import BaseModel

from app.contracts.search import Candidate


class FinalAnswerInput(BaseModel):
    query: str
    language: str
    results: list[Candidate]
    explanation: str
