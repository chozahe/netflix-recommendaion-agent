import pytest

from app.search.image_search import (
    _build_query,
    _extract_og_image,
    _extract_wikipedia_poster,
    search_poster,
)


class TestBuildQuery:
    def test_basic_title_only(self):
        assert _build_query("Inception") == '"Inception"'

    def test_with_movie_type(self):
        assert _build_query("Inception", content_type="Movie") == '"Inception" film'

    def test_with_tv_show_type(self):
        assert _build_query("Stranger Things", content_type="TV Show") == '"Stranger Things" TV series'

    def test_with_year_and_type(self):
        assert _build_query("Inception", content_type="Movie", release_year=2010) == '"Inception" film 2010'


class TestExtractWikipediaPoster:
    def test_extracts_poster_from_infobox(self):
        html = '''
        <html><body>
        <table class="infobox vevent">
        <tr><td><img src="//upload.wikimedia.org/wikipedia/en/thumb/2/2e/Inception_poster.jpg/250px-Inception_poster.jpg"></td></tr>
        </table>
        </body></html>
        '''
        result = _extract_wikipedia_poster(html)
        assert result == "https://upload.wikimedia.org/wikipedia/en/2/2e/Inception_poster.jpg"

    def test_returns_none_without_infobox(self):
        html = '<html><body><img src="//upload.wikimedia.org/image.jpg"></body></html>'
        assert _extract_wikipedia_poster(html) is None

    def test_returns_none_without_images(self):
        html = '<html><body><table class="infobox"></table></body></html>'
        assert _extract_wikipedia_poster(html) is None


class TestExtractOgImage:
    def test_extracts_og_image_from_html(self):
        html = '<html><meta property="og:image" content="https://example.com/poster.jpg"></head></html>'
        assert _extract_og_image(html) == "https://example.com/poster.jpg"

    def test_extracts_reversed_attribute_order(self):
        html = '<html><meta content="https://example.com/poster2.jpg" property="og:image"></head></html>'
        assert _extract_og_image(html) == "https://example.com/poster2.jpg"

    def test_returns_none_when_no_og_image(self):
        html = '<html><head></head></html>'
        assert _extract_og_image(html) is None


class TestSearchPoster:
    def test_returns_none_when_no_results(self, monkeypatch):
        monkeypatch.setattr(
            "app.search.image_search.search_web",
            lambda query, timeout_seconds, max_results: [],
        )
        monkeypatch.setattr(
            "app.search.image_search.curl_requests",
            None,
        )
        assert search_poster("Unknown Title") is None

    def test_returns_wikipedia_poster(self, monkeypatch):
        monkeypatch.setattr(
            "app.search.image_search.search_web",
            lambda query, timeout_seconds, max_results: [
                {"title": "Inception (film) - Wikipedia", "href": "https://en.wikipedia.org/wiki/Inception", "body": "..."},
            ],
        )
        monkeypatch.setattr(
            "app.search.image_search._fetch_page",
            lambda url, timeout: '''
            <table class="infobox vevent">
            <tr><td><img src="//upload.wikimedia.org/wikipedia/en/thumb/2/2e/Inception_poster.jpg/250px-Inception_poster.jpg"></td></tr>
            </table>
            ''',
        )
        assert search_poster("Inception") == "https://upload.wikimedia.org/wikipedia/en/2/2e/Inception_poster.jpg"

    def test_fallbacks_to_og_image(self, monkeypatch):
        monkeypatch.setattr(
            "app.search.image_search.search_web",
            lambda query, timeout_seconds, max_results: [
                {"title": "Inception - IMDb", "href": "https://imdb.com/title/tt1375666", "body": "..."},
            ],
        )
        monkeypatch.setattr(
            "app.search.image_search._fetch_page",
            lambda url, timeout: '<meta property="og:image" content="https://imdb.com/poster.jpg">',
        )
        assert search_poster("Inception") == "https://imdb.com/poster.jpg"

    def test_returns_none_on_fetch_failure(self, monkeypatch):
        monkeypatch.setattr(
            "app.search.image_search.search_web",
            lambda query, timeout_seconds, max_results: [
                {"title": "Inception", "href": "https://example.com", "body": "..."},
            ],
        )
        monkeypatch.setattr(
            "app.search.image_search._fetch_page",
            lambda url, timeout: None,
        )
        assert search_poster("Inception") is None

    def test_returns_none_on_exception(self, monkeypatch):
        monkeypatch.setattr(
            "app.search.image_search.search_web",
            lambda query, timeout_seconds, max_results: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert search_poster("Inception") is None
