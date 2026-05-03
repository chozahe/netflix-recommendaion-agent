def classify_turn(message: str, state: str) -> str:
    text = message.lower()

    if state == "recommended" and any(token in text for token in ["отстой", "слишком", "не ", "нет"]):
        return "feedback_rejection"
    if state == "awaiting_clarification":
        return "clarification_answer"
    if state == "refining":
        return "refinement"
    return "fresh_query"
