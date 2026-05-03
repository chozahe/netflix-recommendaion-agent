from app.contracts.search import Candidate, SearchResult


def test_search_result_contains_candidates_and_status():
    result = SearchResult(
        status="ok",
        selected=[
            Candidate(
                title="Gravity",
                type="Movie",
                release_year=2013,
                country="United States",
                rating="PG-13",
                duration="91 min",
                listed_in="Sci-Fi & Fantasy",
                description="A medical engineer survives in orbit.",
                cast="",
                match_features={"description_overlap": 0.8},
            )
        ],
        discarded=[],
        explanation="Picked strongest space-survival match",
    )

    assert result.status == "ok"
    assert result.selected[0].title == "Gravity"
