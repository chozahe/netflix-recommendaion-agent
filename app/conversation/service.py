from pathlib import Path

from app.contracts.conversation import ConversationResponse
from app.memory.models import ConversationTurn, SessionMemory
from app.memory.session_store import FileSessionStore
from app.orchestration.pipeline import run_analyst, run_finalizer, run_searcher


class ConversationService:
    def __init__(self, store: FileSessionStore):
        self.store = store

    @classmethod
    def for_tests(cls, sessions_dir: str | Path) -> "ConversationService":
        return cls(FileSessionStore(sessions_dir))

    def start_session(self) -> SessionMemory:
        return self.store.create_session()

    def load_session(self, session_id: str) -> SessionMemory:
        return self.store.load_session(session_id)

    def handle_message(self, session_id: str, message: str) -> ConversationResponse:
        session = self.store.load_session(session_id)
        session.turns.append(ConversationTurn(role="user", message=message))

        intent = run_analyst(message)
        session.current_intent = intent

        if intent.needs_clarification:
            session.state = "awaiting_clarification"
            self.store.save_session(session)
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message=intent.clarification_question or "Please clarify your request.",
                recommendations=[],
                state=session.state,
            )

        search_output = run_searcher(intent, last_tool_result={})
        final_message = run_finalizer(message, intent, search_output)
        session.state = "recommended"
        self.store.save_session(session)
        return ConversationResponse(
            type="recommendations",
            session_id=session.session_id,
            message=final_message,
            recommendations=session.last_recommendations,
            state=session.state,
        )
