from app.memory.models import SessionMemory


def test_session_memory_tracks_preference_history():
    memory = SessionMemory(session_id="s1")
    memory.accepted_soft_preferences["vibe"] = ["mysterious"]
    memory.external_signal_history.append("era:1980s")
    assert memory.accepted_soft_preferences["vibe"] == ["mysterious"]
    assert "era:1980s" in memory.external_signal_history
