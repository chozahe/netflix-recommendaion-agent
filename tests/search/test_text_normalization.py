from app.search.text import normalize_text, tokenize_query


def test_normalize_text_lowercases_and_removes_punctuation():
    assert normalize_text("Interstellar!!!") == "interstellar"


def test_tokenize_query_handles_cyrillic_and_latin_text():
    tokens = tokenize_query("мрачное sci-fi про космос")
    assert "мрачное" in tokens
    assert "sci" in tokens or "sci-fi" in tokens
    assert "космос" in tokens
