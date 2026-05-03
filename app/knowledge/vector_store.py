import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings

logger = logging.getLogger(__name__)


class NetflixVectorStore:
    """ChromaDB-backed semantic search over kb/*.md knowledge files.

    At startup, scans all Markdown files in kb/, chunks them by heading
    boundaries, embeds with sentence-transformers, and stores in a
    persistent ChromaDB collection. Supports ``query(text)`` for
    cosine-similarity lookups.

    The local Chroma directory is treated as a rebuildable cache. If the
    persistent state is unreadable or stale, it is deleted and rebuilt from
    ``kb/*.md``.
    """

    COLLECTION_NAME = "netflix_knowledge"
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    _collection: chromadb.Collection

    def __init__(
        self,
        kb_path: Optional[str] = None,
        chroma_path: Optional[str] = None,
    ) -> None:
        kb_path = Path(kb_path or settings.kb_path)
        chroma_path = Path(chroma_path or settings.chroma_path)

        client = self._create_healthy_client(chroma_path)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.EMBEDDING_MODEL,
        )

        try:
            client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass

        self._collection = client.create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=ef,
            metadata={"description": "Netflix recommendation knowledge base"},
        )

        documents, metadatas, ids = self._load_kb_files(kb_path)

        if documents:
            self._collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(
                "NetflixVectorStore indexed %d chunks from kb/", len(documents),
            )
        else:
            logger.warning("NetflixVectorStore: no kb/*.md files found — collection is empty")

    @classmethod
    def _create_healthy_client(cls, chroma_path: Path):
        chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(chroma_path))
        try:
            client.list_collections()
            return client
        except Exception as exc:
            logger.warning("Repairing broken Chroma cache at %s: %s", chroma_path, exc)
            shutil.rmtree(chroma_path, ignore_errors=True)
            chroma_path.mkdir(parents=True, exist_ok=True)
            return chromadb.PersistentClient(path=str(chroma_path))

    # ------------------------------------------------------------------
    # Query entry point
    # ------------------------------------------------------------------
    def query(self, text: str, n_results: int = 3) -> list[dict]:
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[text],
            n_results=min(n_results, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        formatted: list[dict] = []
        docs = results["documents"] or [[]]
        metas = results["metadatas"] or [[]]
        dists = results["distances"] or [[]]

        for doc, meta, dist in zip(docs[0], metas[0], dists[0]):
            formatted.append(
                {
                    "content": doc,
                    "metadata": meta or {},
                    "distance": round(dist, 4),
                }
            )

        return formatted

    @property
    def count(self) -> int:
        return self._collection.count()

    @staticmethod
    def _load_kb_files(kb_path: Path) -> tuple[list[str], list[dict], list[str]]:
        documents: list[str] = []
        metadatas: list[dict] = []
        ids: list[str] = []

        if not kb_path.exists() or not kb_path.is_dir():
            return documents, metadatas, ids

        for md_file in sorted(kb_path.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning("Skipping non-UTF-8 file: %s", md_file)
                continue

            chunks = NetflixVectorStore._chunk_markdown(content, md_file.name)
            for chunk in chunks:
                chunk_id = f"{md_file.stem}_{chunk['chunk_index']}"
                documents.append(chunk["content"])
                metadatas.append(chunk["metadata"])
                ids.append(chunk_id)

        return documents, metadatas, ids

    @staticmethod
    def _chunk_markdown(content: str, filename: str) -> list[dict]:
        chunks: list[dict] = []
        sections = re.split(r"\n(?=#{2,3}\s)", content)
        first_section_offset = 1 if sections[0].strip().startswith("# ") else 0

        chunk_index = 0
        for section in sections[first_section_offset:]:
            section = section.strip()
            if not section:
                continue

            heading_line = section.split("\n", 1)[0].lstrip("#").strip()
            body = section.split("\n", 1)[1] if "\n" in section else ""
            base_meta = {
                "source": filename,
                "section": heading_line,
            }

            table_rows = [
                ln.strip() for ln in body.split("\n")
                if ln.strip().startswith("|") and ln.strip().endswith("|")
                and not re.match(r"^\|[\s\-:]+\|", ln.strip())
            ]
            if len(table_rows) >= 3:
                header_row = table_rows[0]
                data_rows = table_rows[1:]
                for j, row in enumerate(data_rows):
                    doc = f"{heading_line}\n{header_row}\n{row}"
                    meta = {**base_meta, "chunk_index": chunk_index, "table_row": j}
                    chunks.append({"content": doc, "metadata": meta, "chunk_index": chunk_index})
                    chunk_index += 1
            elif len(section) >= 30:
                meta = {**base_meta, "chunk_index": chunk_index}
                chunks.append({"content": section, "metadata": meta, "chunk_index": chunk_index})
                chunk_index += 1

        return chunks


_knowledge_store: Optional[NetflixVectorStore] = None


def get_knowledge_store() -> NetflixVectorStore:
    global _knowledge_store
    if _knowledge_store is None:
        _knowledge_store = NetflixVectorStore()
    return _knowledge_store
