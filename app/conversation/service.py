import json
import time
from pathlib import Path

from app.contracts.analyst import AnalystIntent
from app.contracts.conversation import ConversationResponse
from app.contracts.feedback import FeedbackSignal
from app.memory.merge import is_relaxed_clarification_answer, merge_clarification_answer
from app.memory.models import ConversationTurn, SessionMemory, StoredRecommendation
from app.memory.session_store import FileSessionStore
from app.monitoring import get_logger
from app.orchestration.pipeline import (
    maybe_enrich_search_output,
    run_analyst,
    run_finalizer,
    run_searcher,
)

_logger = get_logger(__name__)


class ConversationService:
    def __init__(self, store: FileSessionStore):
        self.store = store

    @classmethod
    def for_tests(cls, sessions_dir: str | Path) -> "ConversationService":
        return cls(FileSessionStore(sessions_dir))

    @staticmethod
    def _append_memory_preference(target: dict, key: str, value: str) -> None:
        current = list(target.get(key, []))
        if value not in current:
            current.append(value)
        target[key] = current

    @staticmethod
    def _extend_unique_items(target: list[str], values: list[str]) -> None:
        for value in values:
            if value not in target:
                target.append(value)

    def _remember_intent_preferences(self, session: SessionMemory, intent: AnalystIntent) -> None:
        for key, values in (intent.soft_preferences or {}).items():
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str):
                        self._append_memory_preference(session.accepted_soft_preferences, key, value)
        self._extend_unique_items(session.external_signal_history, list(intent.external_signals or []))

    def _log_turn_common(self, session: SessionMemory, extra: dict | None = None) -> dict:
        return {
            "session_id": session.session_id,
            "turn_index": session.analytics.turn_count,
            "state": session.state,
            "clarification_count": session.clarification_count,
            "shown_titles_count": len(session.shown_titles),
            "feedback_signals_count": len(session.feedback_signals),
            "accepted_preferences_keys": list(session.accepted_soft_preferences.keys()),
            "rejected_preferences_keys": list(session.rejected_soft_preferences.keys()),
            "external_signal_count": len(session.external_signal_history),
            **(extra or {}),
        }

    def start_session(self) -> SessionMemory:
        session = self.store.create_session()
        _logger.info("chat_session_started", session_id=session.session_id)
        return session

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
        session.analytics.mark_turn_started()
        session.turns.append(ConversationTurn(role="user", message=message))

        _logger.info("chat_turn_started", **self._log_turn_common(session, {
            "user_message_length": len(message),
        }))

        started = time.perf_counter()
        try:
            response = self._dispatch_message(session, message)
            latency_ms = int((time.perf_counter() - started) * 1000)
            session.analytics.mark_turn_completed(latency_ms=latency_ms, response_type=response.type)

            if response.type == "clarification":
                _logger.info("clarification_requested", **self._log_turn_common(session, {
                    "response_type": response.type,
                    "latency_ms": latency_ms,
                }))
            elif response.type in ("recommendations", "refined_recommendations"):
                rec_count = len(response.recommendations)
                _logger.info("recommendations_generated", **self._log_turn_common(session, {
                    "response_type": response.type,
                    "latency_ms": latency_ms,
                    "recommendation_count": rec_count,
                    "has_posters": any(r.poster_url for r in response.recommendations),
                }))

            _logger.info("chat_turn_completed", **self._log_turn_common(session, {
                "response_type": response.type,
                "latency_ms": latency_ms,
            }))

            self.store.save_session(session)
            return response
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            session.analytics.mark_error()
            _logger.error("chat_turn_failed", **self._log_turn_common(session, {
                "error": str(exc),
                "latency_ms": latency_ms,
            }))
            self.store.save_session(session)
            raise

    def _dispatch_message(self, session: SessionMemory, message: str) -> ConversationResponse:
        feedback = self._parse_feedback(message)
        if session.state == "recommended" and feedback is not None:
            return self._handle_feedback(session, message, feedback)

        if session.state == "awaiting_clarification":
            prior_intent = session.current_intent
            prior_missing_slots = list((prior_intent.missing_slots if prior_intent is not None else []) or [])
            merged_intent = merge_clarification_answer(session, message)
            if merged_intent is not None:
                resolved_content_type = (
                    prior_intent is not None
                    and "content_type" in prior_missing_slots
                    and merged_intent.content_type is not None
                )
                if (
                    is_relaxed_clarification_answer(message)
                    or session.clarification_count >= 2
                    or resolved_content_type
                ):
                    session.analytics.mark_recommendation_round(
                        titles_count=0,
                        unique_titles=len(session.shown_titles),
                    )
                    return self._build_recommendation_response(
                        session=session,
                        intent=merged_intent,
                        message=message,
                        response_type="recommendations",
                    )

                refreshed_intent = run_analyst(merged_intent.query)
                refreshed_intent.clarification_count = session.clarification_count
                session.current_intent = refreshed_intent
                if refreshed_intent.needs_clarification and session.clarification_count < 2:
                    session.clarification_count += 1
                    refreshed_intent.clarification_count = session.clarification_count
                    session.state = "awaiting_clarification"
                    session.analytics.mark_clarification()
                    return ConversationResponse(
                        type="clarification",
                        session_id=session.session_id,
                        message=refreshed_intent.clarification_question or "Please clarify your request.",
                        recommendations=[],
                        state=session.state,
                    )

                session.analytics.mark_recommendation_round(
                    titles_count=0,
                    unique_titles=len(session.shown_titles),
                )
                return self._build_recommendation_response(
                    session=session,
                    intent=refreshed_intent,
                    message=message,
                    response_type="recommendations",
                )

        intent = run_analyst(message)
        session.current_intent = intent

        if intent.needs_clarification:
            session.clarification_count += 1
            intent.clarification_count = session.clarification_count
            session.state = "awaiting_clarification"
            session.analytics.mark_clarification()
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message=intent.clarification_question or "Please clarify your request.",
                recommendations=[],
                state=session.state,
            )

        session.analytics.mark_recommendation_round(
            titles_count=0,
            unique_titles=len(session.shown_titles),
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
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message="Что именно не подошло: возраст, жанр или темп?",
                recommendations=[],
                state=session.state,
            )

        intent = self._build_refined_intent(session, feedback)
        if intent is None:
            return ConversationResponse(
                type="clarification",
                session_id=session.session_id,
                message="Что именно не подошло: возраст, жанр или темп?",
                recommendations=[],
                state=session.state,
            )

        session.analytics.mark_refinement()
        _logger.info("refinement_generated", **self._log_turn_common(session))
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

        if "age:newer" in feedback.values or (feedback.kind == "age" and feedback.value == "newer"):
            hard_constraints["year_from"] = max(hard_constraints.get("year_from", 0), 2018)
            self._append_memory_preference(session.rejected_soft_preferences, "age", "old")
        if "pace:faster" in feedback.values or (feedback.kind == "pace" and feedback.value == "faster"):
            soft_preferences["pace"] = ["fast"]
            self._append_memory_preference(session.rejected_soft_preferences, "pace", "slow")
        if feedback.kind == "type":
            if "сериал" in (feedback.value or ""):
                intent.content_type = "TV Show"
            elif "фильм" in (feedback.value or ""):
                intent.content_type = "Movie"

        for key, values in session.accepted_soft_preferences.items():
            if key not in soft_preferences:
                soft_preferences[key] = list(values)

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
        enriched_output = maybe_enrich_search_output(intent, search_output)
        serialized_output = json.dumps(enriched_output, ensure_ascii=False)
        recommendations = self._extract_recommendations(serialized_output)
        finalizer_output = run_finalizer(message, intent, serialized_output)
        final_message = finalizer_output.get("message", "")
        recommendations = self._merge_posters(recommendations, finalizer_output.get("posters", []))
        self._remember_intent_preferences(session, intent)
        session.current_intent = intent
        session.last_recommendations = recommendations
        intent.clarification_count = session.clarification_count
        session.shown_titles.extend(
            [item.title for item in recommendations if item.title not in session.shown_titles]
        )
        session.state = "recommended"

        if enriched_output.get("enrichment_used"):
            session.analytics.mark_enrichment_used()

        session.analytics.mark_recommendation_round(
            titles_count=len(recommendations),
            unique_titles=len(session.shown_titles),
        )
        return ConversationResponse(
            type=response_type,
            session_id=session.session_id,
            message=final_message,
            recommendations=recommendations,
            state=session.state,
        )

    @staticmethod
    def _merge_posters(
        recommendations: list[StoredRecommendation],
        posters: list[dict],
    ) -> list[StoredRecommendation]:
        by_title = {p["title"]: p.get("poster_url") for p in posters if isinstance(p, dict) and "title" in p}
        for rec in recommendations:
            if rec.title in by_title:
                rec.poster_url = by_title[rec.title]
        return recommendations

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

        values: list[str] = []
        kind = "generic_rejection"
        value: str | None = None

        if "стар" in text or "old" in text:
            values.append("age:newer")
            kind = "age"
            value = "newer"
        if "медлен" in text or "slow" in text:
            values.append("pace:faster")
            if kind == "generic_rejection":
                kind = "pace"
                value = "faster"
        if "сериал" in text or "фильм" in text:
            if kind == "generic_rejection":
                kind = "type"
                value = text

        return FeedbackSignal(
            kind=kind,
            value=value,
            values=values,
            requires_refinement=bool(values or kind == "type"),
        )
