from pathlib import Path

from app.contracts.conversation import ConversationResponse
from app.contracts.feedback import FeedbackSignal
from app.memory.models import ConversationTurn, SessionMemory, StoredRecommendation
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

    def seed_recommendations(self, session_id: str, titles: list[str]) -> SessionMemory:
        session = self.store.load_session(session_id)
        session.last_recommendations = [StoredRecommendation(title=title) for title in titles]
        session.shown_titles.extend(titles)
        session.state = "recommended"
        self.store.save_session(session)
        return session

    def handle_message(self, session_id: str, message: str) -> ConversationResponse:
        session = self.store.load_session(session_id)
        session.turns.append(ConversationTurn(role="user", message=message))

        feedback = self._parse_feedback(message)
        if session.state == "recommended" and feedback is not None:
            session.feedback_signals.append(feedback)
            session.rejected_titles.extend(
                [item.title for item in session.last_recommendations if item.title not in session.rejected_titles]
            )
            session.state = "refining"
            self.store.save_session(session)
            if feedback.requires_refinement:
                response = ConversationResponse(
                    type="refined_recommendations",
                    session_id=session.session_id,
                    message="Окей, давайте попробуем что-то поновее или ближе к вашим пожеланиям.",
                    recommendations=[],
                    state=session.state,
                )
                self.store.save_session(session)
                return response
            response = ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message="Что именно не подошло: возраст, жанр или темп?",
                recommendations=[],
                state=session.state,
            )
            self.store.save_session(session)
            return response

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

    def _parse_feedback(self, message: str) -> FeedbackSignal | None:
        text = message.lower()
        is_negative = any(token in text for token in ["отстой", "не", "слишком", "bad", "boring"])
        if not is_negative:
            return None
        if "стар" in text or "old" in text:
            return FeedbackSignal(kind="age", value="newer", requires_refinement=True)
        if "медлен" in text or "slow" in text:
            return FeedbackSignal(kind="pace", value="faster", requires_refinement=True)
        if "сериал" in text or "фильм" in text:
            return FeedbackSignal(kind="type", value=text, requires_refinement=True)
        return FeedbackSignal(kind="generic_rejection", value=None, requires_refinement=False)
