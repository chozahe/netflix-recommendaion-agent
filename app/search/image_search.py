from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from app.config import settings
from app.search.web_search import search_web

try:  # pragma: no cover
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover
    curl_requests = None


def _build_query(title: str, content_type: str | None = None, release_year: int | None = None) -> str:
    parts = [f'"{title}"']
    if content_type == "Movie":
        parts.append("film")
    elif content_type == "TV Show":
        parts.append("TV series")
    if release_year:
        parts.append(str(release_year))
    return " ".join(parts)


def _fetch_page(url: str, timeout: int) -> str | None:
    if curl_requests is None:
        return None
    try:
        resp = curl_requests.get(url, impersonate="chrome131", timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _extract_wikipedia_poster(html: str) -> str | None:
    """Extract theatrical poster from Wikipedia infobox."""
    # Find infobox table
    infobox_match = re.search(
        r'<table[^>]*class=["\'][^"\']*infobox[^"\']*["\'][^>]*>(.*?)</table>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not infobox_match:
        return None
    infobox = infobox_match.group(1)

    # Find all images in infobox, prefer larger ones that look like posters
    images = re.findall(
        r'<img[^>]*src=["\'](//upload\.wikimedia\.org/wikipedia/[^"\']+)["\'][^>]*>',
        infobox,
        re.IGNORECASE,
    )
    for src in images:
        url = "https:" + src
        # Skip tiny icons (less than 50px wide in the thumbnail URL)
        if re.search(r'/\d+px-', url):
            # Convert thumbnail URL to full-size URL
            # /thumb/.../500px-file.jpg -> /.../file.jpg
            full_url = re.sub(r'/thumb/(.+)/\d+px-[^/]+$', r'/\1', url)
            return full_url
    return None


def _extract_og_image(html: str) -> str | None:
    """Extract OpenGraph image from HTML."""
    match = re.search(
        r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    match = re.search(
        r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    return None


def _search_poster_via_web(title: str, content_type: str | None, timeout: int) -> str | None:
    """Search web results and extract poster from known pages."""
    query = _build_query(title, content_type)

    # Try search_web first (uses DDGS library)
    snippets = search_web(query, timeout_seconds=timeout, max_results=5)

    # Fallback: direct DDG web search with curl_cffi when DDGS is rate-limited
    if not snippets and curl_requests is not None:
        try:
            resp = curl_requests.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                impersonate="chrome131",
                timeout=timeout,
            )
            resp.raise_for_status()
            html = resp.text
            # Extract result links from DDG HTML
            links = re.findall(
                r'<a[^>]*class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                html,
                re.IGNORECASE | re.DOTALL,
            )
            snippets = []
            for href, title_html in links[:5]:
                # Clean up title (remove HTML tags)
                clean_title = re.sub(r'<[^>]+>', '', title_html)
                # Decode DDG redirect URLs
                match = re.search(r'uddg=([^&]+)', href)
                if match:
                    actual_href = unquote(match.group(1))
                else:
                    actual_href = href
                snippets.append({"title": clean_title, "href": actual_href, "body": ""})
        except Exception:
            pass

    if not snippets:
        return None

    # Reorder snippets: prioritize Wikipedia and known movie DBs
    def _priority(snippet: dict) -> int:
        url = snippet.get("href", "").lower()
        if "wikipedia.org" in url:
            return 0
        if "imdb.com" in url or "rottentomatoes.com" in url:
            return 1
        if "britannica.com" in url:
            return 2
        if "warnerbros.com" in url or "official" in snippet.get("title", "").lower():
            return 100  # Deprioritize official studio sites (often logos)
        return 50

    snippets.sort(key=_priority)

    # Try known sources first
    for snippet in snippets:
        url = snippet.get("href", "")
        if "wikipedia.org" in url.lower():
            html = _fetch_page(url, timeout=timeout)
            if html:
                poster = _extract_wikipedia_poster(html)
                if poster:
                    return poster

    # Fallback: any result with og:image (skip studio homepages)
    for snippet in snippets:
        url = snippet.get("href", "")
        if url and ("wikipedia.org" not in url.lower()):
            html = _fetch_page(url, timeout=timeout)
            if html:
                poster = _extract_og_image(html)
                if poster and not _looks_like_logo(poster):
                    return poster

    return None


def _looks_like_logo(url: str) -> bool:
    """Heuristic to detect studio/brand logos vs movie posters."""
    url_lower = url.lower()
    logo_indicators = ["logo", "wordmark", "brand", "icon", "favicon"]
    return any(ind in url_lower for ind in logo_indicators)


def search_poster(
    title: str,
    content_type: str | None = None,
    release_year: int | None = None,
    max_results: int = 5,
    timeout_seconds: int | None = None,
) -> str | None:
    if settings.web_enrichment_provider != "duckduckgo":
        return None

    timeout = timeout_seconds or settings.web_enrichment_timeout_seconds

    try:
        return _search_poster_via_web(title, content_type, timeout=timeout)
    except Exception:
        return None
