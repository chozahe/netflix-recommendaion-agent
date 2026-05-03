import shutil
import subprocess

from app.config import settings
from app.conversation.service import ConversationService


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

    print("Netflix chat started. Type 'exit' or 'quit' to stop.")
    while True:
        message = input("> ").strip()
        if message.lower() in {"exit", "quit"}:
            print("Bye!")
            return
        if not message:
            continue

        response = service.handle_message(session.session_id, message)
        print(format_agent_reply(response.model_dump()))
