from app.tools.filter_candidates import filter_candidate_rows


def test_filter_candidate_rows_keeps_only_titles_after_year_threshold():
    rows = [
        {"title": "A", "release_year": 2010, "country": "US"},
        {"title": "B", "release_year": 2020, "country": "US"},
    ]

    filtered = filter_candidate_rows(rows, hard_filters={"year_from": 2015})

    assert [row["title"] for row in filtered] == ["B"]
