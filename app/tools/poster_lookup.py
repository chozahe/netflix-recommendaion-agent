import json as json_module
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.search.image_search import search_poster


class PosterLookupInput(BaseModel):
    title: str = Field(..., description="Verified title to look up a poster for.")
    content_type: Optional[str] = Field(default=None, description="Content type: 'Movie' or 'TV Show'.")
    release_year: Optional[int] = Field(default=None, description="Release year to improve search precision.")


class PosterLookupTool(BaseTool):
    name: str = "PosterLookup"
    description: str = (
        "Look up a poster image URL for a verified title using DuckDuckGo image search. "
        "Only use for titles already returned by Searcher. Returns a poster_url or null."
    )
    args_schema: Type[BaseModel] = PosterLookupInput

    def _run(
        self,
        title: str,
        content_type: Optional[str] = None,
        release_year: Optional[int] = None,
    ) -> str:
        poster_url = search_poster(
            title=title,
            content_type=content_type,
            release_year=release_year,
        )
        return json_module.dumps({"poster_url": poster_url}, ensure_ascii=False)
