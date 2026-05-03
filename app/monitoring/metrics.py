from prometheus_client import Counter, Histogram, start_http_server

REQUESTS_TOTAL = Counter(
    "netflix_agent_requests_total",
    "Total recommendation requests",
    ["status"],
)

REQUEST_DURATION = Histogram(
    "netflix_agent_request_duration_seconds",
    "Request duration in seconds",
    buckets=(1, 5, 10, 15, 20, 30, 45, 60, 90, 120),
)

TOKENS_TOTAL = Counter(
    "netflix_agent_tokens_total",
    "Total tokens used by agent",
    ["agent"],
)

CHAT_SESSIONS_TOTAL = Counter(
    "netflix_agent_chat_sessions_total",
    "Total chat sessions started",
)

CHAT_TURNS_TOTAL = Counter(
    "netflix_agent_chat_turns_total",
    "Total chat turns processed",
    ["status", "type"],
)

CHAT_TURN_DURATION = Histogram(
    "netflix_agent_chat_turn_duration_seconds",
    "Chat turn duration in seconds",
    buckets=(0.5, 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120),
)

CLARIFICATIONS_TOTAL = Counter(
    "netflix_agent_clarifications_total",
    "Total clarification turns requested",
)

REFINEMENTS_TOTAL = Counter(
    "netflix_agent_refinements_total",
    "Total refinement rounds triggered",
)

RECOMMENDATIONS_TOTAL = Counter(
    "netflix_agent_recommendations_total",
    "Total recommendation rounds completed",
)

FALLBACKS_TOTAL = Counter(
    "netflix_agent_fallbacks_total",
    "Total fallback activations",
    ["stage"],
)


def setup_metrics(port: int) -> None:
    try:
        start_http_server(port)
    except OSError:
        pass
