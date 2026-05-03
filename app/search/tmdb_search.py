from __future__ import annotations

from typing import Any

import requests

from app.config import settings

TMDB_BASE = "https://api.themoviedb.org/3"


def _tmdb_image_url(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/w500{poster_path}"


def _tmdb_get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    key = settings.tmdb_api_key
    if not key:
        return None
    try:
        resp = requests.get(
            f"{TMDB_BASE}{path}",
            params={**params, "api_key": key},
            timeout=settings.web_enrichment_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def search_tmdb_poster(title: str, content_type: str | None = None) -> str | None:
    data = _tmdb_get("/search/multi", {"query": title})
    if not data:
        return None

    results = data.get("results", [])
    if not results:
        return None

    # Try to match content type
    for item in results:
        media_type = item.get("media_type")
        if content_type == "Movie" and media_type != "movie":
            continue
        if content_type == "TV Show" and media_type not in ("tv",):
            continue
        path = item.get("poster_path")
        if path:
            return _tmdb_image_url(path)

    # Fallback: any result with a poster
    for item in results:
        path = item.get("poster_path")
        if path:
            return _tmdb_image_url(path)

    return None
