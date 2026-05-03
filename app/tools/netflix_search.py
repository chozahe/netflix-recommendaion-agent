import json as json_module
from typing import Optional, Type

import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings
from app.search import CatalogSearchEngine


class NetflixSearchInput(BaseModel):
    content_type: Optional[str] = Field(default=None, description="Filter by type: 'Movie' or 'TV Show'.")
    year_from: Optional[int] = Field(default=None, description="Minimum release year (inclusive).")
    year_to: Optional[int] = Field(default=None, description="Maximum release year (inclusive).")
    country: Optional[str] = Field(default=None, description="Country name for partial match on the 'country' column.")
    rating: Optional[str] = Field(default=None, description="Exact age rating.")
    genre: Optional[str] = Field(default=None, description="Genre for partial match on the 'listed_in' column.")
    text_query: Optional[str] = Field(default=None, description="Free-text search query.")
    mode: str = Field(default="hybrid", description="Search mode: title, description, listed_in, cast, or hybrid.")
    limit: int = Field(default=10, description="Maximum number of results to return (default 10, max 20).")


class NetflixSearchTool(BaseTool):
    name: str = "NetflixSearch"
    description: str = (
        "Search the Netflix catalog using transparent retrieval routes: title, description, "
        "listed_in, cast, or hybrid. Hard filters are applied before scoring."
    )
    args_schema: Type[BaseModel] = NetflixSearchInput

    _df: pd.DataFrame
    _engine: CatalogSearchEngine

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        raw = pd.read_csv(settings.netflix_csv_path)
        raw["rating"] = raw["rating"].apply(self._sanitize_rating)
        self._df = raw
        self._engine = CatalogSearchEngine(self._df)

    @staticmethod
    def _sanitize_rating(value) -> Optional[str]:
        if pd.isna(value):
            return None
        value = str(value).strip()
        duration_like = any(c.isdigit() for c in value) and "min" in value.lower()
        if duration_like:
            return None
        return value

    def _run(
        self,
        content_type: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        country: Optional[str] = None,
        rating: Optional[str] = None,
        genre: Optional[str] = None,
        text_query: Optional[str] = None,
        mode: str = "hybrid",
        limit: int = 10,
    ) -> str:
        hard_filters = {
            "content_type": content_type,
            "year_from": year_from,
            "year_to": year_to,
            "country": country,
            "rating": rating,
            "genre": genre,
        }
        results = self._engine.search(
            query=text_query or "",
            mode=mode,
            hard_filters=hard_filters,
            limit=limit,
        )

        filters_applied = [f"{key}={value}" for key, value in hard_filters.items() if value not in (None, "")]
        if text_query:
            filters_applied.append(f"mode={mode}")
            filters_applied.append(f"text~{text_query}")

        return json_module.dumps(
            {
                "count": len(results),
                "filters_applied": filters_applied,
                "results": results,
            },
            ensure_ascii=False,
        )
