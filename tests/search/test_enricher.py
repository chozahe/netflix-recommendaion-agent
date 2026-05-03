from app.search.enricher import should_enrich_results



def test_vibe_heavy_query_can_enable_enrichment():
    assert should_enrich_results("мрачный атмосферный sci-fi", candidate_count=5) is True
