from fastapi.testclient import TestClient
from app.api.server import app



def test_post_chat_returns_structured_response():
    client = TestClient(app)
    session = client.post("/sessions").json()
    response = client.post("/chat", json={
        "session_id": session["session_id"],
        "message": "хочу что-нибудь мрачное",
    })
    assert response.status_code == 200
    assert "type" in response.json()
