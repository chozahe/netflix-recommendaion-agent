import pandas as pd

from app.search.catalog import CatalogSearchEngine


def test_title_route_prefers_exact_title_match():
    df = pd.DataFrame(
        [
            {
                "title": "Interstellar",
                "type": "Movie",
                "release_year": 2014,
                "country": "United States",
                "rating": "PG-13",
                "duration": "169 min",
                "listed_in": "Sci-Fi & Fantasy",
                "description": "Explorers travel through a wormhole",
                "cast": "",
            },
            {
                "title": "The Stars at Noon",
                "type": "Movie",
                "release_year": 2022,
                "country": "France",
                "rating": "R",
                "duration": "138 min",
                "listed_in": "Dramas",
                "description": "A journalist gets trapped abroad",
                "cast": "",
            },
        ]
    )
    engine = CatalogSearchEngine(df)

    results = engine.search(query="interstellar", mode="title", hard_filters={}, limit=5)

    assert results[0]["title"] == "Interstellar"
    assert results[0]["match_features"]["title_exact"] is True


def test_description_route_returns_descriptive_space_matches():
    df = pd.DataFrame(
        [
            {
                "title": "Gravity",
                "type": "Movie",
                "release_year": 2013,
                "country": "United States",
                "rating": "PG-13",
                "duration": "91 min",
                "listed_in": "Sci-Fi & Fantasy",
                "description": "A woman survives alone in space after a disaster",
                "cast": "",
            },
            {
                "title": "Chef",
                "type": "Movie",
                "release_year": 2014,
                "country": "United States",
                "rating": "R",
                "duration": "114 min",
                "listed_in": "Comedies",
                "description": "A chef starts a food truck",
                "cast": "",
            },
        ]
    )
    engine = CatalogSearchEngine(df)

    results = engine.search(query="space survival", mode="description", hard_filters={}, limit=5)

    assert results[0]["title"] == "Gravity"
    assert results[0]["match_features"]["description_overlap"] > 0
