import json as json_module
from typing import Optional, Type

import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.config import settings


class NetflixSearchInput(BaseModel):
    content_type: Optional[str] = Field(
        default=None,
        description="Filter by type: 'Movie' or 'TV Show'. Apply this filter FIRST.",
    )
    year_from: Optional[int] = Field(
        default=None,
        description="Minimum release year (inclusive). Apply this filter SECOND.",
    )
    year_to: Optional[int] = Field(
        default=None,
        description="Maximum release year (inclusive). Apply this filter SECOND.",
    )
    country: Optional[str] = Field(
        default=None,
        description=(
            "Country name for partial match on the 'country' column. "
            "E.g. 'United States' matches 'United States, Canada'. "
            "Apply this filter THIRD."
        ),
    )
    rating: Optional[str] = Field(
        default=None,
        description=(
            "Exact age rating. One of: G, PG, PG-13, R, NC-17, NR, UR, "
            "TV-Y, TV-Y7, TV-Y7-FV, TV-G, TV-PG, TV-14, TV-MA. "
            "Apply this filter FOURTH."
        ),
    )
    genre: Optional[str] = Field(
        default=None,
        description=(
            "Genre for partial match on the 'listed_in' column. "
            "E.g. 'Comedies' matches 'TV Comedies, Stand-Up Comedy'. "
            "Apply this filter FIFTH."
        ),
    )
    text_query: Optional[str] = Field(
        default=None,
        description=(
            "Free-text search across title, description, and cast columns. "
            "Each word is required (AND logic). Useful when the user mentions "
            "specific plot details, actor names, or title keywords. "
            "Apply this filter LAST."
        ),
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return (default 10, max 20).",
    )


class NetflixSearchTool(BaseTool):
    name: str = "NetflixSearch"
    description: str = (
        "Search the Netflix catalog (8807 titles) by type, year, country, rating, "
        "genre, and free-text query. Returns matching movies and TV shows with full details. "
        "Apply filters in order: type → year → country → rating → genre → text_query. "
        "All filters are optional — filters with None value are skipped."
    )
    args_schema: Type[BaseModel] = NetflixSearchInput

    _df: pd.DataFrame

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        csv_path = settings.netflix_csv_path
        raw = pd.read_csv(csv_path)

        raw["rating"] = raw["rating"].apply(self._sanitize_rating)
        raw["country"] = raw["country"].fillna("")
        raw["listed_in"] = raw["listed_in"].fillna("")
        raw["description"] = raw["description"].fillna("")
        raw["cast"] = raw["cast"].fillna("")
        raw["title"] = raw["title"].fillna("")

        self._df = raw

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
        limit: int = 10,
    ) -> str:
        df = self._df.copy()
        filters_applied = []

        if content_type and content_type in ("Movie", "TV Show"):
            df = df[df["type"] == content_type]
            filters_applied.append(f"type={content_type}")

        if year_from is not None or year_to is not None:
            y_from = year_from if year_from is not None else 1900
            y_to = year_to if year_to is not None else 2100
            df = df[df["release_year"].between(y_from, y_to)]
            filters_applied.append(f"year=[{y_from}, {y_to}]")

        if country:
            df = df[df["country"].str.contains(country, case=False, na=False)]
            filters_applied.append(f"country~{country}")

        if rating:
            valid_ratings = df["rating"].dropna().unique()
            if rating in valid_ratings:
                df = df[df["rating"] == rating]
                filters_applied.append(f"rating={rating}")

        if genre:
            df = df[df["listed_in"].str.contains(genre, case=False, na=False)]
            filters_applied.append(f"genre~{genre}")

        if text_query:
            words = [w.strip().lower() for w in text_query.split() if len(w.strip()) > 1]
            if words:
                text_cols = df["title"] + " | " + df["description"] + " | " + df["cast"]
                # Build a relevance mask — count how many query words match each row.
                hit_mask = pd.Series(0, index=df.index)
                for word in words:
                    hit_mask += text_cols.str.contains(word, case=False, na=False).astype(int)
                # Keep rows with at least 1 hit, then sort by relevance (most hits first)
                df = df[hit_mask >= 1]
                df = df.iloc[(-hit_mask[df.index]).argsort()]
                filters_applied.append(f"text~{text_query}")

        limit = min(limit, 20)
        df = df.head(limit)

        fields = [
            "title",
            "type",
            "release_year",
            "country",
            "rating",
            "duration",
            "listed_in",
            "description",
            "cast",
        ]
        results = df[fields].fillna("").to_dict(orient="records")

        return json_module.dumps(
            {
                "count": len(results),
                "filters_applied": filters_applied,
                "results": results,
            },
            ensure_ascii=False,
        )
