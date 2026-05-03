# Agentic Search Redesign Implementation Plan

> **REQUIRED SUB-SKILL:** Use the executing-plans skill to implement this plan task-by-task.

**Goal:** Rebuild the Netflix recommendation agent into a real 3-agent, tool-driven, local-first system with better descriptive search and flexible OpenCode Go model routing.

**Architecture:** Keep the linear `Analyst -> Searcher -> Finalizer` pipeline, but replace hidden search logic in `app/main.py` with explicit contracts, a small search backend, transparent tools, and thin orchestration. Make Searcher the real multi-step tool-using agent, keep retrieval primitives deterministic, and add a universal LLM adapter for both OpenAI-compatible and Anthropic-style endpoints.

**Tech Stack:** Python 3.11, CrewAI, Pydantic, pandas, ChromaDB, LangChain/OpenAI-compatible clients, httpx, pytest

---

## Phase 1 — Foundations

### Task 1: Add test harness and contract scaffolding

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/contracts/test_analyst_contracts.py`
- Create: `tests/contracts/test_search_contracts.py`
- Create: `app/contracts/__init__.py`
- Create: `app/contracts/analyst.py`
- Create: `app/contracts/search.py`
- Create: `app/contracts/finalizer.py`

**Step 1: Write the failing test**

```python
from app.contracts.analyst import AnalystIntent
from app.contracts.search import Candidate, SearchResult


def test_analyst_intent_accepts_hard_and_soft_constraints():
    intent = AnalystIntent(
        query="что-нибудь мрачное про космос",
        content_type=None,
        hard_constraints={"year_from": None, "year_to": None},
        soft_preferences={"mood": ["dark"], "topics": ["space"]},
        topic_hypotheses=["space survival"],
        genre_hypotheses=["Sci-Fi & Fantasy"],
        mood_hypotheses=["dark"],
        language="ru",
        explanation="Detected space topic and dark mood",
    )
    assert intent.language == "ru"
    assert intent.soft_preferences["topics"] == ["space"]


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/contracts/test_analyst_contracts.py tests/contracts/test_search_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.contracts'`

**Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class AnalystIntent(BaseModel):
    query: str
    content_type: str | None = None
    hard_constraints: dict
    soft_preferences: dict
    topic_hypotheses: list[str]
    genre_hypotheses: list[str]
    mood_hypotheses: list[str]
    language: str
    explanation: str
```

```python
from pydantic import BaseModel


class Candidate(BaseModel):
    title: str
    type: str
    release_year: int
    country: str
    rating: str | None = None
    duration: str | None = None
    listed_in: str = ""
    description: str = ""
    cast: str = ""
    match_features: dict = {}


class SearchResult(BaseModel):
    status: str
    selected: list[Candidate]
    discarded: list[Candidate]
    explanation: str
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/contracts/test_analyst_contracts.py tests/contracts/test_search_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/conftest.py tests/contracts/test_analyst_contracts.py tests/contracts/test_search_contracts.py app/contracts/__init__.py app/contracts/analyst.py app/contracts/search.py app/contracts/finalizer.py
git commit -m "test: add contract scaffolding"
```

### Task 2: Add local-first runtime bootstrap and remove Docker

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/runtime/test_bootstrap.py`
- Create: `app/runtime/__init__.py`
- Create: `app/runtime/bootstrap.py`
- Modify: `app/config.py`
- Modify: `README.md`
- Modify: `.env.example`
- Delete: `Dockerfile`
- Delete: `docker-compose.yml`

**Step 1: Write the failing test**

```python
from pathlib import Path

from app.runtime.bootstrap import ensure_runtime_ready


def test_ensure_runtime_ready_creates_runtime_directories(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    chroma_dir = tmp_path / "chroma_db"
    ensure_runtime_ready(logs_dir=logs_dir, chroma_dir=chroma_dir)
    assert logs_dir.exists()
    assert chroma_dir.exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/runtime/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.runtime'`

**Step 3: Write minimal implementation**

```python
from pathlib import Path


def ensure_runtime_ready(*, logs_dir: Path, chroma_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)
```

Also update docs/config so local setup is the only supported path and Docker instructions are removed.

**Step 4: Run test to verify it passes**

Run: `pytest tests/runtime/test_bootstrap.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/runtime/test_bootstrap.py app/runtime/__init__.py app/runtime/bootstrap.py app/config.py README.md .env.example
git rm Dockerfile docker-compose.yml
git commit -m "refactor: make runtime local-first"
```

## Phase 2 — Search backend

### Task 3: Build text normalization helpers for search

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/search/test_text_normalization.py`
- Create: `app/search/__init__.py`
- Create: `app/search/text.py`

**Step 1: Write the failing test**

```python
from app.search.text import normalize_text, tokenize_query


def test_normalize_text_lowercases_and_removes_punctuation():
    assert normalize_text("Interstellar!!!") == "interstellar"


def test_tokenize_query_handles_cyrillic_and_latin_text():
    tokens = tokenize_query("мрачное sci-fi про космос")
    assert "мрачное" in tokens
    assert "sci" in tokens or "sci-fi" in tokens
    assert "космос" in tokens
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/search/test_text_normalization.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.search'`

**Step 3: Write minimal implementation**

```python
import re


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize_query(text: str) -> list[str]:
    return [token for token in normalize_text(text).split() if len(token) > 1]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/search/test_text_normalization.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/search/test_text_normalization.py app/search/__init__.py app/search/text.py
git commit -m "feat: add search text normalization"
```

### Task 4: Build candidate retrieval primitives with title and descriptive routes

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/search/test_catalog_search.py`
- Create: `app/search/catalog.py`
- Modify: `app/tools/netflix_search.py`

**Step 1: Write the failing test**

```python
import pandas as pd

from app.search.catalog import CatalogSearchEngine


def test_title_route_prefers_exact_title_match():
    df = pd.DataFrame(
        [
            {"title": "Interstellar", "type": "Movie", "release_year": 2014, "country": "United States", "rating": "PG-13", "duration": "169 min", "listed_in": "Sci-Fi & Fantasy", "description": "Explorers travel through a wormhole", "cast": ""},
            {"title": "The Stars at Noon", "type": "Movie", "release_year": 2022, "country": "France", "rating": "R", "duration": "138 min", "listed_in": "Dramas", "description": "A journalist gets trapped abroad", "cast": ""},
        ]
    )
    engine = CatalogSearchEngine(df)
    results = engine.search(query="interstellar", mode="title", hard_filters={}, limit=5)
    assert results[0]["title"] == "Interstellar"
    assert results[0]["match_features"]["title_exact"] is True


def test_description_route_returns_descriptive_space_matches():
    df = pd.DataFrame(
        [
            {"title": "Gravity", "type": "Movie", "release_year": 2013, "country": "United States", "rating": "PG-13", "duration": "91 min", "listed_in": "Sci-Fi & Fantasy", "description": "A woman survives alone in space after a disaster", "cast": ""},
            {"title": "Chef", "type": "Movie", "release_year": 2014, "country": "United States", "rating": "R", "duration": "114 min", "listed_in": "Comedies", "description": "A chef starts a food truck", "cast": ""},
        ]
    )
    engine = CatalogSearchEngine(df)
    results = engine.search(query="space survival", mode="description", hard_filters={}, limit=5)
    assert results[0]["title"] == "Gravity"
    assert results[0]["match_features"]["description_overlap"] > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/search/test_catalog_search.py -v`
Expected: FAIL with `ImportError` for `CatalogSearchEngine`

**Step 3: Write minimal implementation**

```python
class CatalogSearchEngine:
    def __init__(self, df):
        self._df = df.copy()

    def search(self, query: str, mode: str, hard_filters: dict, limit: int = 10) -> list[dict]:
        # Implement route-specific scoring for title / description / listed_in / hybrid.
        # Return sorted candidate dicts with `match_features`.
        ...
```

Refactor `app/tools/netflix_search.py` into a thin wrapper around `CatalogSearchEngine` instead of keeping search logic inside the tool itself.

**Step 4: Run test to verify it passes**

Run: `pytest tests/search/test_catalog_search.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/search/test_catalog_search.py app/search/catalog.py app/tools/netflix_search.py
git commit -m "feat: add catalog search primitives"
```

### Task 5: Add transparent Searcher tools

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/tools/test_search_tools.py`
- Create: `app/tools/filter_candidates.py`
- Create: `app/tools/inspect_candidate.py`
- Modify: `app/tools/knowledge_search.py`
- Modify: `app/tools/__init__.py`

**Step 1: Write the failing test**

```python
from app.tools.filter_candidates import filter_candidate_rows


def test_filter_candidate_rows_keeps_only_titles_after_year_threshold():
    rows = [
        {"title": "A", "release_year": 2010, "country": "US"},
        {"title": "B", "release_year": 2020, "country": "US"},
    ]
    filtered = filter_candidate_rows(rows, hard_filters={"year_from": 2015})
    assert [row["title"] for row in filtered] == ["B"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_search_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.tools.filter_candidates'`

**Step 3: Write minimal implementation**

```python
def filter_candidate_rows(rows: list[dict], hard_filters: dict) -> list[dict]:
    year_from = hard_filters.get("year_from")
    if year_from is None:
        return rows
    return [row for row in rows if row.get("release_year", 0) >= year_from]
```

Then wrap this logic in CrewAI `BaseTool` classes so Searcher can use:
- `SearchCatalogTool`
- `FilterCandidatesTool`
- `InspectCandidateTool`
- `KnowledgeSearchTool`

**Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_search_tools.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/tools/test_search_tools.py app/tools/filter_candidates.py app/tools/inspect_candidate.py app/tools/knowledge_search.py app/tools/__init__.py
git commit -m "feat: add transparent search tools"
```

## Phase 3 — Agents and model routing

### Task 6: Replace ad-hoc LLM factory with universal provider adapter

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/llm/test_factory.py`
- Create: `app/llm/providers.py`
- Modify: `app/llm/factory.py`
- Modify: `app/config.py`

**Step 1: Write the failing test**

```python
from app.llm.factory import classify_model_backend


def test_classify_model_backend_supports_openai_compatible_models():
    assert classify_model_backend("qwen3.5-plus") == "openai"


def test_classify_model_backend_supports_anthropic_style_models():
    assert classify_model_backend("deepseek-v4-pro") == "anthropic"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_factory.py -v`
Expected: FAIL with `ImportError` or missing `classify_model_backend`

**Step 3: Write minimal implementation**

```python
ANTHROPIC_STYLE_MODELS = {"deepseek-v4-pro", "deepseek-v4-flash", "minimax-m2.5", "minimax-m2.7"}


def classify_model_backend(model: str) -> str:
    clean = model.replace("openai/", "").replace("anthropic/", "").replace("opencode-go/", "")
    return "anthropic" if clean in ANTHROPIC_STYLE_MODELS else "openai"
```

Then build provider adapters behind one public interface and support role-based profiles for Analyst/Searcher/Finalizer.

**Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/llm/test_factory.py app/llm/providers.py app/llm/factory.py app/config.py
git commit -m "refactor: add universal llm provider layer"
```

### Task 7: Rebuild agents around explicit contracts and Searcher tool loop

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/agents/test_agent_payloads.py`
- Create: `app/agents/definitions.py`
- Create: `app/orchestration/__init__.py`
- Create: `app/orchestration/pipeline.py`
- Modify: `app/agents/__init__.py`
- Modify: `app/main.py`
- Modify: `prompts/analyst.md`
- Modify: `prompts/searcher.md`
- Modify: `prompts/finalizer.md`

**Step 1: Write the failing test**

```python
from app.contracts.analyst import AnalystIntent
from app.orchestration.pipeline import build_searcher_input


def test_build_searcher_input_passes_only_query_intent_and_last_tool_result():
    intent = AnalystIntent(
        query="что-нибудь мрачное про космос",
        content_type=None,
        hard_constraints={},
        soft_preferences={"topics": ["space"]},
        topic_hypotheses=["space survival"],
        genre_hypotheses=["Sci-Fi & Fantasy"],
        mood_hypotheses=["dark"],
        language="ru",
        explanation="Detected dark space request",
    )
    payload = build_searcher_input(intent=intent, last_tool_result={"candidates": []})
    assert payload["query"] == intent.query
    assert payload["intent"]["topic_hypotheses"] == ["space survival"]
    assert payload["last_tool_result"] == {"candidates": []}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_agent_payloads.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.orchestration'`

**Step 3: Write minimal implementation**

```python
def build_searcher_input(intent, last_tool_result: dict) -> dict:
    return {
        "query": intent.query,
        "intent": intent.model_dump(),
        "last_tool_result": last_tool_result,
    }
```

Then move orchestration out of `app/main.py`, build agent definitions in dedicated modules, and wire Searcher with real tools instead of precomputed results.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_agent_payloads.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/agents/test_agent_payloads.py app/agents/definitions.py app/orchestration/__init__.py app/orchestration/pipeline.py app/agents/__init__.py app/main.py prompts/analyst.md prompts/searcher.md prompts/finalizer.md
git commit -m "refactor: rebuild agent orchestration around tool loop"
```

## Phase 4 — Verification and evaluation

### Task 8: Add eval scaffolding and local verification flow

**TDD scenario:** New feature — full TDD cycle

**Files:**
- Create: `tests/evals/test_smoke_queries.py`
- Create: `app/evals/run_evals.py`
- Modify: `app/evals/__init__.py`
- Modify: `README.md`

**Step 1: Write the failing test**

```python
from app.evals.run_evals import EVAL_QUERIES


def test_eval_queries_cover_descriptive_and_title_search():
    assert any("космос" in query for query in EVAL_QUERIES)
    assert any("interstellar" in query.lower() for query in EVAL_QUERIES)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/evals/test_smoke_queries.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.evals.run_evals'`

**Step 3: Write minimal implementation**

```python
EVAL_QUERIES = [
    "что-нибудь мрачное про космос",
    "interstellar",
    "легкий сериал на вечер",
]
```

Then add a local eval runner that exercises the pipeline and prints basic relevance / no-result / latency signals for manual comparison across model profiles.

**Step 4: Run test to verify it passes**

Run: `pytest tests/evals/test_smoke_queries.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/evals/test_smoke_queries.py app/evals/run_evals.py app/evals/__init__.py README.md
git commit -m "feat: add local eval scaffolding"
```

## Checkpoint verification

After Task 8, run the full local verification suite:

```bash
pytest -v
python -m app.main "что-нибудь мрачное про космос"
python -m app.main "interstellar"
python -m app.evals.run_evals
```

Expected:
- tests pass
- local CLI runs without Docker
- descriptive query returns sensible verified candidates
- title query finds exact or near-exact title matches
- eval runner executes with the configured model profile

## Suggested commit cadence

- Commit after every task exactly as written
- If Task 4 or Task 7 grows too large, split before coding, not during coding
- Keep Searcher logic thin enough that prompt changes do not require touching the search engine internals

## Notes for the implementer

- Do not reintroduce Docker files
- Do not hide retry strategy inside `app/main.py`
- Do not build a monolithic “smart” search engine that chooses results for the agent
- Keep tool outputs compact for budget models
- Prefer deterministic code for retrieval and filtering, agent reasoning for strategy
- Preserve the project term **knowledges** when referring to the ChromaDB knowledge layer
