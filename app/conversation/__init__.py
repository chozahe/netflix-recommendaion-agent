from app.conversation.classifier import classify_turn
from app.conversation.state_machine import (
    AWAITING_CLARIFICATION,
    IDLE,
    RECOMMENDED,
    REFINING,
)

__all__ = [
    "classify_turn",
    "ConversationService",
    "IDLE",
    "AWAITING_CLARIFICATION",
    "RECOMMENDED",
    "REFINING",
]


def __getattr__(name: str):
    if name == "ConversationService":
        from app.conversation.service import ConversationService

        return ConversationService
    raise AttributeError(name)
