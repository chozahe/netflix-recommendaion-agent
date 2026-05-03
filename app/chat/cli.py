from app.config import settings
from app.conversation.service import ConversationService



def format_agent_reply(response: dict) -> str:
    return response.get("message", "")



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
