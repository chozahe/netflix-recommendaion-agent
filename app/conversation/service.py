import json
from pathlib import Path

from app.contracts.analyst import AnalystIntent
from app.contracts.conversation import ConversationResponse
from app.contracts.feedback import FeedbackSignal
from app.memory.merge import merge_clarification_answer
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
            return self._handle_feedback(session, message, feedback)

        if session.state == "awaiting_clarification":
            merged_intent = merge_clarification_answer(session, message)
            if merged_intent is not None:
                return self._build_recommendation_response(
                    session=session,
                    intent=merged_intent,
                    message=message,
                    response_type="recommendations",
                )

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

        return self._build_recommendation_response(
            session=session,
            intent=intent,
            message=message,
            response_type="recommendations",
        )

    def _handle_feedback(
        self,
        session: SessionMemory,
        message: str,
        feedback: FeedbackSignal,
    ) -> ConversationResponse:
        session.feedback_signals.append(feedback)
        session.rejected_titles.extend(
            [item.title for item in session.last_recommendations if item.title not in session.rejected_titles]
        )
        session.state = "refining"

        if not feedback.requires_refinement:
            self.store.save_session(session)
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message="Что именно не подошло: возраст, жанр или темп?",
                recommendations=[],
                state=session.state,
            )

        intent = self._build_refined_intent(session, feedback)
        if intent is None:
            self.store.save_session(session)
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message="Что именно не подошло: возраст, жанр или темп?",
                recommendations=[],
                state=session.state,
            )

        return self._build_recommendation_response(
            session=session,
            intent=intent,
            message=message,
            response_type="refined_recommendations",
        )

    def _build_refined_intent(
        self,
        session: SessionMemory,
        feedback: FeedbackSignal,
    ) -> AnalystIntent | None:
        intent = session.current_intent
        if intent is None:
            return None

        hard_constraints = dict(intent.hard_constraints or {})
        soft_preferences = dict(intent.soft_preferences or {})

        if feedback.kind == "age" and feedback.value == "newer":
            hard_constraints["year_from"] = max(hard_constraints.get("year_from", 0), 2018)
        elif feedback.kind == "pace" and feedback.value == "faster":
            soft_preferences["pace"] = ["fast"]
        elif feedback.kind == "type":
            if "сериал" in (feedback.value or ""):
                intent.content_type = "TV Show"
            elif "фильм" in (feedback.value or ""):
                intent.content_type = "Movie"

        intent.hard_constraints = hard_constraints
        intent.soft_preferences = soft_preferences
        intent.needs_clarification = False
        intent.clarification_question = None
        intent.missing_slots = []
        session.current_intent = intent
        return intent

    def _build_recommendation_response(
        self,
        session: SessionMemory,
        intent,
        message: str,
        response_type: str,
    ) -> ConversationResponse:
        search_output = run_searcher(intent, last_tool_result={})
        recommendations = self._extract_recommendations(search_output)
        final_message = run_finalizer(message, intent, search_output)
        session.current_intent = intent
        session.last_recommendations = recommendations
        session.shown_titles.extend(
            [item.title for item in recommendations if item.title not in session.shown_titles]
        )
        session.state = "recommended"
        self.store.save_session(session)
        return ConversationResponse(
            type=response_type,
            session_id=session.session_id,
            message=final_message,
            recommendations=recommendations,
            state=session.state,
        )

    def _extract_recommendations(self, search_output: str) -> list[StoredRecommendation]:
        try:
            payload = json.loads(search_output)
        except json.JSONDecodeError:
            return []

        selected = payload.get("selected", [])
        recommendations: list[StoredRecommendation] = []
        for item in selected:
            if isinstance(item, dict) and item.get("title"):
                recommendations.append(
                    StoredRecommendation(title=item["title"], reason=item.get("reason"))
                )
        return recommendations

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
