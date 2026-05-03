from app.search.enricher import should_enrich_results



def test_vibe_heavy_query_can_enable_enrichment():
    assert should_enrich_results("мрачный атмосферный sci-fi", candidate_count=5) is True


def test_should_enrich_when_intent_contains_external_signals():
    assert should_enrich_results(
        query="сериал с вайбом 80-х",
        candidate_count=3,
        external_signals=["era:1980s", "actor:winona_ryder"],
    ) is True
