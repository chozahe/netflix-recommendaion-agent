import pytest

from app.search.tmdb_search import _tmdb_image_url, search_tmdb_poster


class TestTmdbImageUrl:
    def test_builds_full_url(self):
        assert _tmdb_image_url("/abc123.jpg") == "https://image.tmdb.org/t/p/w500/abc123.jpg"

    def test_returns_none_for_empty_path(self):
        assert _tmdb_image_url("") is None
        assert _tmdb_image_url(None) is None


class TestSearchTmdbPoster:
    def test_returns_poster_url_for_movie(self, monkeypatch):
        def mock_get(url, params, timeout):
            class Response:
                def json(self):
                    return {
                        "results": [
                            {"media_type": "movie", "title": "Inception", "poster_path": "/inception.jpg"}
                        ]
                    }
                def raise_for_status(self): pass
            return Response()

        monkeypatch.setattr("app.search.tmdb_search.requests.get", mock_get)
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", "test_key")
        assert search_tmdb_poster("Inception") == "https://image.tmdb.org/t/p/w500/inception.jpg"

    def test_filters_by_content_type_tv(self, monkeypatch):
        def mock_get(url, params, timeout):
            class Response:
                def json(self):
                    return {
                        "results": [
                            {"media_type": "movie", "title": "Inception", "poster_path": "/movie.jpg"},
                            {"media_type": "tv", "name": "Stranger Things", "poster_path": "/tv.jpg"},
                        ]
                    }
                def raise_for_status(self): pass
            return Response()

        monkeypatch.setattr("app.search.tmdb_search.requests.get", mock_get)
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", "test_key")
        assert search_tmdb_poster("Stranger Things", content_type="TV Show") == "https://image.tmdb.org/t/p/w500/tv.jpg"

    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", None)
        assert search_tmdb_poster("Inception") is None

    def test_returns_none_when_no_results(self, monkeypatch):
        def mock_get(url, params, timeout):
            class Response:
                def json(self): return {"results": []}
                def raise_for_status(self): pass
            return Response()

        monkeypatch.setattr("app.search.tmdb_search.requests.get", mock_get)
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", "test_key")
        assert search_tmdb_poster("Unknown Movie") is None

    def test_returns_none_on_http_error(self, monkeypatch):
        def mock_get(url, params, timeout):
            class Response:
                def raise_for_status(self):
                    raise RuntimeError("HTTP 429")
            return Response()

        monkeypatch.setattr("app.search.tmdb_search.requests.get", mock_get)
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", "test_key")
        assert search_tmdb_poster("Inception") is None

    def test_fallback_to_any_poster_when_type_mismatch(self, monkeypatch):
        def mock_get(url, params, timeout):
            class Response:
                def json(self):
                    return {
                        "results": [
                            {"media_type": "movie", "title": "Something", "poster_path": "/fallback.jpg"},
                        ]
                    }
                def raise_for_status(self): pass
            return Response()

        monkeypatch.setattr("app.search.tmdb_search.requests.get", mock_get)
        monkeypatch.setattr("app.search.tmdb_search.settings.tmdb_api_key", "test_key")
        # Even if we ask for TV Show but TMDB only has movie result, fallback to it
        assert search_tmdb_poster("Something", content_type="TV Show") == "https://image.tmdb.org/t/p/w500/fallback.jpg"
