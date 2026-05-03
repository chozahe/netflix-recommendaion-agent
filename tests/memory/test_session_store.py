from app.memory.session_store import FileSessionStore



def test_file_session_store_persists_session(tmp_path):
    store = FileSessionStore(tmp_path)
    session = store.create_session()
    loaded = store.load_session(session.session_id)
    assert loaded.session_id == session.session_id
