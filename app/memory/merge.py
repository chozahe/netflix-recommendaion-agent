from app.contracts.analyst import AnalystIntent
from app.memory.models import SessionMemory



def merge_clarification_answer(memory: SessionMemory, message: str) -> AnalystIntent | None:
    intent = memory.current_intent
    if intent is None:
        return None

    text = message.lower()
    if "сериал" in text or "tv" in text or "show" in text:
        intent.content_type = "TV Show"
    elif "фильм" in text or "movie" in text:
        intent.content_type = "Movie"

    intent.query = f"{intent.query} {message}".strip()
    intent.needs_clarification = False
    intent.clarification_question = None
    intent.missing_slots = []
    memory.current_intent = intent
    return intent
