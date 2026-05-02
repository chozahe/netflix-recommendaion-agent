import json as json_module
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.knowledge.vector_store import get_knowledge_store


class KnowledgeSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="Search query for the Netflix knowledge base (e.g. 'age ratings for kids', 'genre for space movies')",
    )
    n_results: int = Field(
        default=3,
        description="Number of search results to return (1–5)",
    )


class KnowledgeSearchTool(BaseTool):
    name: str = "KnowledgeSearch"
    description: str = (
        "Search the Netflix knowledge base for genre mappings, rating definitions, "
        "country popularity data, mood keywords, and recommendation safety rules. "
        "Use this when you need to look up which Netflix genre corresponds to a "
        "user theme (e.g. 'space' → 'Sci-Fi & Fantasy'), which ratings are safe "
        "for children, or what country aliases exist."
    )
    args_schema: Type[BaseModel] = KnowledgeSearchInput

    _store: object

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._store = get_knowledge_store()

    def _run(self, query: str, n_results: int = 3) -> str:
        n_results = max(1, min(n_results, 5))
        results = self._store.query(query, n_results=n_results)

        if not results:
            return json_module.dumps(
                {"results": [], "query": query, "message": "No knowledge base matches found"},
                ensure_ascii=False,
            )

        formatted = []
        for i, r in enumerate(results, start=1):
            meta = r.get("metadata", {})
            formatted.append(
                {
                    "rank": i,
                    "source": meta.get("source", "unknown"),
                    "section": meta.get("section", ""),
                    "distance": r.get("distance"),
                    "content": r.get("content", ""),
                }
            )

        return json_module.dumps(
            {"results": formatted, "query": query, "count": len(formatted)},
            ensure_ascii=False,
        )
