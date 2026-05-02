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


def setup_metrics(port: int) -> None:
    try:
        start_http_server(port)
    except OSError:
        pass
