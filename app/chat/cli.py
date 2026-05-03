import shutil
import subprocess

from app.config import settings
from app.conversation.service import ConversationService
from app.monitoring import (
    CHAT_SESSIONS_TOTAL,
    CHAT_TURNS_TOTAL,
    CHAT_TURN_DURATION,
    CLARIFICATIONS_TOTAL,
    REFINEMENTS_TOTAL,
    RECOMMENDATIONS_TOTAL,
    get_logger,
)

_logger = get_logger(__name__)


def _try_inline_image(url: str) -> bool:
    """Attempt to display an image inline in the terminal. Return True on success."""
    if not shutil.which("kitten"):
        return False
    try:
        subprocess.run(
            ["kitten", "icat", "--align=left", url],
            check=True,
            capture_output=True,
            timeout=settings.web_enrichment_timeout_seconds,
        )
        return True
    except Exception:
        return False


def format_agent_reply(response: dict) -> str:
    lines = [response.get("message", "")]
    for rec in response.get("recommendations", []):
        poster_url = rec.get("poster_url")
        if poster_url:
            lines.append("")
            lines.append(f"[{rec.get('title', '')}]")
            try:
                rendered = _try_inline_image(poster_url)
            except Exception:
                rendered = False
            if not rendered:
                lines.append(poster_url)
    return "\n".join(lines)


def run_chat() -> None:
    service = ConversationService.for_tests(settings.sessions_dir)
    session = service.start_session()
    CHAT_SESSIONS_TOTAL.inc()

    _logger.info("chat_loop_started", session_id=session.session_id)

    try:
        while True:
            message = input("> ").strip()
            if message.lower() in {"exit", "quit"}:
                _logger.info("chat_session_ended", session_id=session.session_id)
                print("Bye!")
                return
            if not message:
                continue

            response = service.handle_message(session.session_id, message)
            response_dict = response.model_dump()
            print(format_agent_reply(response_dict))

            resp_type = response.type
            status = "success"
            CHAT_TURNS_TOTAL.labels(status=status, type=resp_type).inc()

            if resp_type == "clarification":
                CLARIFICATIONS_TOTAL.inc()
            elif resp_type == "refined_recommendations":
                REFINEMENTS_TOTAL.inc()
            elif resp_type == "recommendations":
                RECOMMENDATIONS_TOTAL.inc()

            if session.analytics.last_latency_ms > 0:
                CHAT_TURN_DURATION.observe(session.analytics.last_latency_ms / 1000.0)
    except Exception as exc:
        _logger.error("chat_loop_error", session_id=session.session_id, error=str(exc))
        CHAT_TURNS_TOTAL.labels(status="error", type="error").inc()
        raise
