from pathlib import Path

from app.knowledge.vector_store import NetflixVectorStore


class _BrokenClient:
    def list_collections(self):
        raise KeyError("_type")


class _HealthyClient:
    def __init__(self):
        self.created = None

    def list_collections(self):
        return []

    def create_collection(self, name, embedding_function, metadata):
        self.created = (name, metadata)

        class _Collection:
            def add(self, documents, metadatas, ids):
                self.documents = documents

            def count(self):
                return 1

            def query(self, query_texts, n_results, include):
                return {
                    "documents": [["doc"]],
                    "metadatas": [[{"source": "kb.md", "section": "Test"}]],
                    "distances": [[0.1]],
                }

        return _Collection()


def test_vector_store_repairs_broken_persistent_state(monkeypatch, tmp_path: Path):
    stale_file = tmp_path / "stale.txt"
    stale_file.write_text("old-state", encoding="utf-8")

    healthy_client = _HealthyClient()
    clients = iter([_BrokenClient(), healthy_client])

    monkeypatch.setattr(
        "app.knowledge.vector_store.chromadb.PersistentClient",
        lambda path: next(clients),
    )
    monkeypatch.setattr(
        "app.knowledge.vector_store.embedding_functions.SentenceTransformerEmbeddingFunction",
        lambda model_name: object(),
    )
    monkeypatch.setattr(
        NetflixVectorStore,
        "_load_kb_files",
        staticmethod(lambda kb_path: (["chunk"], [{"source": "kb.md", "section": "Test"}], ["id-1"])),
    )

    store = NetflixVectorStore(kb_path=str(tmp_path), chroma_path=str(tmp_path))

    assert stale_file.exists() is False
    assert healthy_client.created[0] == "netflix_knowledge"
    assert store.count == 1
