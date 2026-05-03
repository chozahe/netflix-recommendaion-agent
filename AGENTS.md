# AGENTS.md — Netflix Recommendation Agent

## Terminology
- **catalog search** — deterministic retrieval over `data/netflix_titles.csv`.
- **agentic search loop** — Searcher-driven multi-step tool usage with bounded retries.
- **Analyst** — LLM-only agent (no tools), analyses user query and outputs structured intent directly.

## Current architecture
- 3-agent linear pipeline: **Analyst** → **Searcher** → **Finalizer**.
- Orchestration framework: [CrewAI](https://docs.crewai.com/) with Tools.
- Local-first runtime — **no Docker support**.
- LLM client layer: OpenCode Go via OpenAI-compatible and Anthropic-style adapters.
- Search backend: pandas-backed catalog retrieval with title / description / listed_in / cast / hybrid routes.
- Dataset: `data/netflix_titles.csv` (8807 rows).
- No external knowledge store — Analyst relies on LLM understanding; Searcher uses catalog tools only.

## Current project state
The project is simplified and streamlined. The main implemented layers are:

```text
app/
├── agents/           # Agent builders + prompt loading
├── contracts/        # Pydantic inter-agent schemas
├── evals/            # Local eval runner scaffolding
├── llm/              # Universal provider routing for OpenCode Go models
├── monitoring/       # structlog + Prometheus metrics
├── orchestration/    # Pipeline wiring and deterministic fallbacks
├── runtime/          # Local runtime bootstrap
├── search/           # Catalog retrieval primitives + normalization
├── tools/            # CrewAI tools (NetflixSearch, FilterCandidates, InspectCandidate)
├── config.py         # Environment-backed settings
└── main.py           # Thin local CLI entrypoint
```

## Key architecture rules
1. **Analyst should produce strict machine-readable intent** — using only its own LLM understanding, no external tools.
2. **Searcher must use tools against the real CSV** — never invent titles.
3. **Finalizer must only use verified Searcher output**.
4. **Searcher is bounded** — use small `max_iter` and fallbacks to avoid long loops.
5. **Deterministic fallbacks are allowed** when agent output is empty or invalid.
6. **Local CLI is the primary workflow** — optimize for fast iterative runs, not container deployment.

## Model/runtime conventions
- `OPENAI_BASE_URL` defaults to `https://opencode.ai/zen/go/v1`.
- Use provider-prefixed model names in `.env`, e.g.:
  - `openai/qwen3.5-plus`
  - `openai/deepseek-v4-pro`
  - `openai/deepseek-v4-flash`
- Current recommended interactive profile:
  - Analyst: `openai/qwen3.5-plus`
  - Searcher: `openai/deepseek-v4-pro` or `openai/deepseek-v4-flash` for faster UX
  - Finalizer: `openai/deepseek-v4-flash`
- Guardrails live in config:
  - `LLM_TIMEOUT_SECONDS`
  - `ANALYST_MAX_ITER`
  - `SEARCHER_MAX_ITER`
  - `FINALIZER_MAX_ITER`

## Commands
```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run CLI
python -m app.main "хочу фильм про космос"

# Run evals
python -m app.evals.run_evals

# Metrics (while app is running)
curl http://localhost:8001/metrics

# Tests
pytest -v
```

## Current known workflow notes
- Some eval scenarios may be better run in a separate session to avoid noise from verbose agent logs.
- For very fast UX, prefer smaller Searcher iteration count and faster Searcher model.

## Testing
- Framework: pytest.
- There is now real test coverage for:
  - contracts
  - runtime bootstrap
  - text normalization
  - catalog search
  - search tools
  - LLM backend routing
  - orchestration payload helpers
  - analyst fallback
  - searcher fallback
  - eval scaffolding
- Before claiming completion, always run fresh verification commands.
