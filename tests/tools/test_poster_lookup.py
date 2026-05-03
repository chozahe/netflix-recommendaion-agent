import json

import pytest

from app.tools.poster_lookup import PosterLookupInput, PosterLookupTool


class TestPosterLookupTool:
    def test_tool_returns_poster_url_when_found(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.poster_lookup.search_poster",
            lambda title, content_type=None, release_year=None, max_results=5, timeout_seconds=None: "https://example.com/poster.jpg",
        )
        tool = PosterLookupTool()
        result = tool._run(title="Inception")
        payload = json.loads(result)
        assert payload["poster_url"] == "https://example.com/poster.jpg"

    def test_tool_returns_null_when_not_found(self, monkeypatch):
        monkeypatch.setattr(
            "app.tools.poster_lookup.search_poster",
            lambda title, content_type=None, release_year=None, max_results=5, timeout_seconds=None: None,
        )
        tool = PosterLookupTool()
        result = tool._run(title="Unknown Movie")
        payload = json.loads(result)
        assert payload["poster_url"] is None

    def test_tool_passes_optional_metadata(self, monkeypatch):
        calls = []

        def mock_search(title, content_type=None, release_year=None, max_results=5, timeout_seconds=None):
            calls.append({"title": title, "content_type": content_type, "release_year": release_year})
            return "https://example.com/poster.jpg"

        monkeypatch.setattr("app.tools.poster_lookup.search_poster", mock_search)
        tool = PosterLookupTool()
        tool._run(title="Inception", content_type="Movie", release_year=2010)
        assert len(calls) == 1
        assert calls[0]["title"] == "Inception"
        assert calls[0]["content_type"] == "Movie"
        assert calls[0]["release_year"] == 2010

    def test_tool_never_returns_new_titles(self, monkeypatch):
        """The tool only looks up posters for the given title; it does not discover new titles."""
        monkeypatch.setattr(
            "app.tools.poster_lookup.search_poster",
            lambda title, content_type=None, release_year=None, max_results=5, timeout_seconds=None: None,
        )
        tool = PosterLookupTool()
        result = tool._run(title="Inception")
        payload = json.loads(result)
        assert "title" not in payload or payload.get("title") is None
        assert payload.get("poster_url") is None
