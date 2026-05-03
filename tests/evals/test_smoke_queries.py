from app.evals.run_evals import EVAL_QUERIES


def test_eval_queries_cover_descriptive_and_title_search():
    assert any("космос" in query for query in EVAL_QUERIES)
    assert any("interstellar" in query.lower() for query in EVAL_QUERIES)
