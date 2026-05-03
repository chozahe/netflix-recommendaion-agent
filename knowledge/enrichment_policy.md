# Enrichment Policy

- Never enrich before catalog retrieval.
- Enrichment is optional.
- Run at most one enrichment pass.
- Enrich at most 2-3 shortlisted titles.
- Default provider is bounded DuckDuckGo search over a small number of result snippets.
- Only use title/snippet evidence in the first implementation stage.
- Never introduce new titles from the web into the candidate pool.
- Respect timeout, provider, and feature flag guardrails.
- On provider failure or timeout, degrade gracefully to no enrichment.
