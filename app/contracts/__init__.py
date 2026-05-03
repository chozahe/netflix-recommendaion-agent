from app.contracts.analyst import AnalystIntent
from app.contracts.finalizer import FinalAnswerInput
from app.contracts.search import Candidate, SearchResult

__all__ = [
    "AnalystIntent",
    "Candidate",
    "SearchResult",
    "FinalAnswerInput",
    "ConversationResponse",
    "FeedbackSignal",
]


def __getattr__(name: str):
    if name == "ConversationResponse":
        from app.contracts.conversation import ConversationResponse

        return ConversationResponse
    if name == "FeedbackSignal":
        from app.contracts.feedback import FeedbackSignal

        return FeedbackSignal
    raise AttributeError(name)
