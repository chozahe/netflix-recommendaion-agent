from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.contracts.analyst import AnalystIntent
from app.contracts.feedback import FeedbackSignal


class ConversationTurn(BaseModel):
    role: str
    message: str


class StoredRecommendation(BaseModel):
    title: str
    reason: str | None = None
    poster_url: str | None = None


class SessionAnalytics(BaseModel):
    started_at: str = ""
    last_updated_at: str = ""
    turn_count: int = 0
    user_turn_count: int = 0
    assistant_turn_count: int = 0
    clarification_turn_count: int = 0
    recommendation_round_count: int = 0
    refinement_round_count: int = 0
    error_count: int = 0
    total_latency_ms: int = 0
    last_latency_ms: int = 0
    last_response_type: str = ""
    recommended_titles_count: int = 0
    unique_titles_count: int = 0
    fallback_count: int = 0
    enrichment_used_count: int = 0

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def mark_started(self) -> None:
        ts = self._now_iso()
        self.started_at = ts
        self.last_updated_at = ts

    def mark_turn_started(self) -> None:
        self.turn_count += 1
        self.user_turn_count += 1
        self.last_updated_at = self._now_iso()

    def mark_turn_completed(
        self,
        latency_ms: int,
        response_type: str,
    ) -> None:
        self.assistant_turn_count += 1
        self.last_latency_ms = latency_ms
        self.total_latency_ms += latency_ms
        self.last_response_type = response_type
        self.last_updated_at = self._now_iso()

    def mark_clarification(self) -> None:
        self.clarification_turn_count += 1

    def mark_recommendation_round(self, titles_count: int, unique_titles: int) -> None:
        self.recommendation_round_count += 1
        self.recommended_titles_count += titles_count
        self.unique_titles_count = unique_titles

    def mark_refinement(self) -> None:
        self.refinement_round_count += 1

    def mark_error(self) -> None:
        self.error_count += 1
        self.last_updated_at = self._now_iso()

    def mark_fallback(self) -> None:
        self.fallback_count += 1

    def mark_enrichment_used(self) -> None:
        self.enrichment_used_count += 1


class SessionMemory(BaseModel):
    session_id: str
    state: str = "idle"
    turns: list[ConversationTurn] = Field(default_factory=list)
    shown_titles: list[str] = Field(default_factory=list)
    rejected_titles: list[str] = Field(default_factory=list)
    current_intent: AnalystIntent | None = None
    last_recommendations: list[StoredRecommendation] = Field(default_factory=list)
    feedback_signals: list[FeedbackSignal] = Field(default_factory=list)
    clarification_count: int = 0
    accepted_soft_preferences: dict = Field(default_factory=dict)
    rejected_soft_preferences: dict = Field(default_factory=dict)
    external_signal_history: list[str] = Field(default_factory=list)
    analytics: SessionAnalytics = Field(default_factory=SessionAnalytics)
