import json as json_module
from typing import Any, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class FilterCandidatesInput(BaseModel):
    candidates: list[dict[str, Any]] = Field(..., description="Candidate rows to filter.")
    content_type: Optional[str] = Field(default=None, description="Exact content type filter.")
    year_from: Optional[int] = Field(default=None, description="Minimum release year inclusive.")
    year_to: Optional[int] = Field(default=None, description="Maximum release year inclusive.")
    country: Optional[str] = Field(default=None, description="Country substring filter.")
    rating: Optional[str] = Field(default=None, description="Exact rating filter.")
    genre: Optional[str] = Field(default=None, description="Genre substring filter.")


def filter_candidate_rows(rows: list[dict], hard_filters: dict) -> list[dict]:
    filtered = list(rows)
    content_type = hard_filters.get("content_type")
    if content_type:
        filtered = [row for row in filtered if row.get("type") == content_type]

    year_from = hard_filters.get("year_from")
    if year_from is not None:
        filtered = [row for row in filtered if row.get("release_year") is not None and row.get("release_year") >= year_from]

    year_to = hard_filters.get("year_to")
    if year_to is not None:
        filtered = [row for row in filtered if row.get("release_year") is not None and row.get("release_year") <= year_to]

    country = hard_filters.get("country")
    if country:
        filtered = [row for row in filtered if country.lower() in str(row.get("country", "")).lower()]

    rating = hard_filters.get("rating")
    if rating:
        filtered = [row for row in filtered if row.get("rating") == rating]

    genre = hard_filters.get("genre")
    if genre:
        filtered = [row for row in filtered if genre.lower() in str(row.get("listed_in", "")).lower()]

    return filtered


class FilterCandidatesTool(BaseTool):
    name: str = "FilterCandidates"
    description: str = "Apply transparent hard filters to an existing candidate pool."
    args_schema: Type[BaseModel] = FilterCandidatesInput

    def _run(
        self,
        candidates: list[dict[str, Any]],
        content_type: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        country: Optional[str] = None,
        rating: Optional[str] = None,
        genre: Optional[str] = None,
    ) -> str:
        hard_filters = {
            "content_type": content_type,
            "year_from": year_from,
            "year_to": year_to,
            "country": country,
            "rating": rating,
            "genre": genre,
        }
        filtered = filter_candidate_rows(candidates, hard_filters)
        return json_module.dumps({"count": len(filtered), "results": filtered}, ensure_ascii=False)
