import sys

from fastapi.testclient import TestClient

from app.api.server import app
from app.conversation.service import ConversationService
from app.main import main



def test_clarification_flow_smoke(tmp_path):
    service = ConversationService.for_tests(tmp_path)
    session = service.start_session()

    response = service.handle_message(session.session_id, "хочу что-нибудь мрачное")

    assert response.type == "clarification"
    assert response.state == "awaiting_clarification"



def test_chat_api_happy_path_smoke():
    client = TestClient(app)
    session = client.post("/sessions").json()
    response = client.post(
        "/chat",
        json={
            "session_id": session["session_id"],
            "message": "хочу что-нибудь мрачное",
        },
    )

    assert response.status_code == 200
    assert response.json()["type"] == "clarification"



def test_one_shot_cli_still_works(monkeypatch, capsys):
    monkeypatch.setattr("app.main.run_pipeline", lambda query: f"RESULT: {query}")
    monkeypatch.setattr("app.main.setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.main.setup_metrics", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.main.ensure_runtime_ready", lambda **kwargs: None)
    monkeypatch.setattr("app.main.settings.openai_api_key", "test-key")
    monkeypatch.setattr(sys, "argv", ["app.main", "хочу", "фильм", "про", "космос"])

    main()

    output = capsys.readouterr().out
    assert "RESULT: хочу фильм про космос" in output
