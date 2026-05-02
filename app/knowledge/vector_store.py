import logging
import re
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
    persistent ChromaDB collection.  Supports ``query(text)`` for
    cosine-similarity lookups.

    The collection is rebuilt from scratch on every instantiation because
    the design requires a restart to pick up KB changes (no hot-reload).
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
        chroma_path = chroma_path or settings.chroma_path

        client = chromadb.PersistentClient(path=str(chroma_path))
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
        # ChromaDB returns lists-of-lists for the three include keys
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

    # ------------------------------------------------------------------
    # File loading & chunking
    # ------------------------------------------------------------------
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
        # Split on "## ..." or "### ..." at line start (but not "# ..." which is the file title)
        sections = re.split(r"\n(?=#{2,3}\s)", content)
        # The first "section" is everything before the first heading
        # Skip it if it's just the file-level title / intro
        first_section_offset = 1 if sections[0].strip().startswith("# ") else 0

        chunk_index = 0
        for i, section in enumerate(sections[first_section_offset:]):
            section = section.strip()
            if not section:
                continue

            heading_line = section.split("\n", 1)[0].lstrip("#").strip()
            body = section.split("\n", 1)[1] if "\n" in section else ""
            base_meta = {
                "source": filename,
                "section": heading_line,
            }

            # Detect table: 3+ lines starting with |
            table_rows = [
                ln.strip() for ln in body.split("\n")
                if ln.strip().startswith("|") and ln.strip().endswith("|")
                and not re.match(r"^\|[\s\-:]+\|", ln.strip())
            ]
            # Skip the header row (first data-style row before separator)
            # Keep only data rows
            if len(table_rows) >= 3:
                # table_rows[0] is column header, rest are data
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
