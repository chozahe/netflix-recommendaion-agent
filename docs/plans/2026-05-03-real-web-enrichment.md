# Real Web Enrichment Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Replace the current stubbed enrichment layer with a real bounded web search implementation that validates external signals against search results while preserving DB-first reranking.

**Architecture:** Keep the current flow `Searcher -> maybe_enrich_search_output -> enrich_shortlisted_titles -> enrich_titles`, but replace `app/search/web_search.py` with a real provider-backed search adapter. Use a free no-key provider by default (`duckduckgo_search`) to fetch a small number of search results per shortlisted title, score evidence for `actor:*`, `era:*`, and `vibe:*` signals from snippets/titles, and return structured matches. Never add new titles from the web; only rerank already-retrieved CSV candidates.

**Tech Stack:** Python 3.11, pytest, `duckduckgo_search`, httpx (already present transitively / used in project), CrewAI pipeline, Pydantic.

---

## Phase 1 — Real enrichment adapter

### Task 1: Add failing tests for real web enrichment scoring

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/search/test_web_search.py`
- Modify: `tests/search/test_enrichment_rerank.py`

**Step 1: Write the failing tests**

```python
from app.search.web_search import enrich_titles


def test_enrich_titles_scores_actor_and_era_matches(monkeypatch):
    monkeypatch.setattr(
        "app.search.web_search.search_web",
        lambda query, timeout_seconds, max_results=5: [
            {
                "title": "Stranger Things - Wikipedia",
                "body": "Set in the 1980s and starring Winona Ryder.",
                "href": "https://example.com/stranger-things",
            }
        ],
    )

    enriched = enrich_titles(
        ["Stranger Things"],
        timeout_seconds=5,
        external_signals=["era:1980s", "actor:winona_ryder"],
    )

    assert enriched[0]["title"] == "Stranger Things"
    assert "era:1980s" in enriched[0]["matched_external_signals"]
    assert "actor:winona_ryder" in enriched[0]["matched_external_signals"]
    assert enriched[0]["confidence_boost"] >= 2
```

```python
from app.contracts.analyst import AnalystIntent
from app.orchestration.pipeline import maybe_enrich_search_output


def test_enrichment_marks_used_only_when_real_signal_match_exists(monkeypatch):
    intent = AnalystIntent(
        query="сериал с вайбом 80-х и Вайноной Райдер",
        content_type="TV Show",
        external_signals=["era:1980s", "actor:winona_ryder"],
    )
    search_output = '{"selected":[{"title":"Stranger Things","reason":"cast match"}]}'

    monkeypatch.setattr(
        "app.orchestration.pipeline.enrich_shortlisted_titles",
        lambda query, titles, external_signals=None: [
            {"title": "Stranger Things", "matched_external_signals": [], "confidence_boost": 0}
        ],
    )

    enriched = maybe_enrich_search_output(intent, search_output)
    assert enriched["enrichment_used"] is False
```

**Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/pytest tests/search/test_web_search.py tests/search/test_enrichment_rerank.py -v
```
Expected: FAIL because `search_web` does not exist and `enrichment_used` is currently too optimistic.

**Step 3: Write minimal implementation**

Implement in `app/search/web_search.py`:
- `search_web(query: str, timeout_seconds: int, max_results: int = 5) -> list[dict]`
- default provider: `duckduckgo_search.DDGS().text(...)`
- result normalization: `title`, `body`, `href`
- helper normalization for actor/era/vibe markers
- helper scoring for matched external signals
- `enrich_titles(...)` returns structured evidence with real `matched_external_signals` and non-zero `confidence_boost` only when snippet/title text supports the signals
- graceful fallback to empty enrichment on timeout/provider failure

Update `app/orchestration/pipeline.py` so `enrichment_used=True` only when at least one selected candidate gets a positive match/boost.

**Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/pytest tests/search/test_web_search.py tests/search/test_enrichment_rerank.py -v
```
Expected: PASS

**Step 5: Run focused regressions**

Run:
```bash
.venv/bin/pytest tests/search/test_enricher.py tests/evals/test_association_search_smoke.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add tests/search/test_web_search.py tests/search/test_enrichment_rerank.py app/search/web_search.py app/orchestration/pipeline.py app/search/enricher.py requirements.txt
git commit -m "feat: add real bounded web enrichment search"
```

---

## Phase 2 — Config, docs, and runtime guardrails

### Task 2: Add provider configuration and document the real enrichment behavior

**TDD scenario:** Modifying tested code — run existing tests first

**Files:**
- Modify: `app/config.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `knowledge/enrichment_policy.md`
- Modify: `tests/evals/test_smoke_queries.py`

**Step 1: Run existing tests first**

Run:
```bash
.venv/bin/pytest tests/evals/test_smoke_queries.py -v
```
Expected: PASS

**Step 2: Add failing/expanded test coverage**

Expand `tests/evals/test_smoke_queries.py` to assert that documentation/eval coverage still includes an association-style enrichment query after provider config changes.

**Step 3: Run test to verify it fails if needed**

Run:
```bash
.venv/bin/pytest tests/evals/test_smoke_queries.py -v
```
Expected: FAIL only if test was expanded beyond current config/docs behavior.

**Step 4: Write minimal implementation**

Add to `app/config.py`:
- `web_enrichment_provider: str = os.getenv("WEB_ENRICHMENT_PROVIDER", "duckduckgo")`
- `web_enrichment_search_results: int = env_int("WEB_ENRICHMENT_SEARCH_RESULTS", 5)`

Update docs to explain:
- real provider-backed enrichment now exists
- default is free no-key DuckDuckGo search
- still DB-first, bounded, optional, and rerank-only
- provider failures degrade gracefully to no enrichment

Update `knowledge/enrichment_policy.md` to include:
- search provider is bounded
- only snippet/title evidence is used initially
- no new titles may enter the candidate pool

**Step 5: Run tests to verify they pass**

Run:
```bash
.venv/bin/pytest tests/evals/test_smoke_queries.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add app/config.py README.md AGENTS.md knowledge/enrichment_policy.md tests/evals/test_smoke_queries.py
git commit -m "docs: document real bounded web enrichment provider"
```

---

## Phase 3 — Full verification

### Task 3: Verify end-to-end behavior remains stable

**TDD scenario:** Trivial verification step — use judgment

**Files:**
- No source changes unless verification exposes a defect

**Step 1: Run targeted verification**

Run:
```bash
.venv/bin/pytest tests/search/test_web_search.py tests/search/test_enrichment_rerank.py tests/search/test_enricher.py tests/evals/test_association_search_smoke.py -v
```
Expected: PASS

**Step 2: Run full verification**

Run:
```bash
.venv/bin/pytest -q
printf 'quit\n' | .venv/bin/python -m app.chat_main
.venv/bin/python -m app.main "посоветуй сериал с вайбом 80-х и Вайноной Райдер"
```
Expected:
- all tests pass
- chat starts
- one-shot flow returns recommendation output

**Step 3: Commit if verification required code fixes**

```bash
git add <changed-files>
git commit -m "fix: stabilize real web enrichment verification"
```

---

## Notes for execution

- Keep YAGNI: do not build a generic crawling framework.
- Keep DB-first: web never introduces titles.
- Prefer free no-key provider first (`duckduckgo_search`) before paid APIs.
- Scoring should be deterministic and transparent.
- Timeout or provider failure must never break recommendation flow.
- Initial version may score from search result titles/snippets only; page fetching can be a later upgrade if needed.
