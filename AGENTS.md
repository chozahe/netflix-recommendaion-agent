# AGENTS.md — Netflix Recommendation Agent

## Terminology
- **catalog search** — deterministic retrieval over `data/netflix_titles.csv`.
- **agentic search loop** — Searcher-driven multi-step tool usage with bounded retries.
- **Analyst** — LLM-only agent (no tools), analyses user query and outputs structured intent directly.

## Current architecture
- 3-agent linear pipeline: **Analyst** → **Searcher** → **Finalizer**, wrapped in **ConversationService** for multi-turn dialog.
- Analyst-led clarification: analyst decides when clarification is needed (max 2 turns), with relaxed-answer detection (`любое / пофиг / не важно`).
- Bounded DB-first enrichment: optional post-retrieval reranking of CSV candidates via external signals, never inventing new titles.
- Session memory with accumulating preference memory (`accepted_soft_preferences`, `rejected_soft_preferences`, `external_signal_history`).
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
├── api/              # FastAPI chat API
├── chat/             # Interactive CLI chat
├── chat_main.py      # Chat CLI entrypoint
├── config.py         # Environment-backed settings
├── contracts/        # Pydantic inter-agent schemas (AnalystIntent, ConversationResponse, etc.)
├── conversation/     # ConversationService, clarification, classifier
├── evals/            # Local eval runner scaffolding
├── llm/              # Universal provider routing for OpenCode Go models
├── main.py           # Thin local CLI entrypoint
├── memory/           # SessionMemory models + FileSessionStore
├── monitoring/       # structlog + Prometheus metrics
├── orchestration/    # Pipeline wiring + maybe_enrich_search_output + fallbacks
├── runtime/          # Local runtime bootstrap
├── search/           # Catalog retrieval + enricher + web_search stub
└── tools/            # CrewAI tools (NetflixSearch, FilterCandidates, InspectCandidate)
```

## Key architecture rules
1. **Analyst should produce strict machine-readable intent** — using only its own LLM understanding, no external tools.
2. **Analyst decides clarification** — local code does not short-circuit; analyst outputs `needs_clarification`, `confidence`, `external_signals`.
3. **Searcher must use tools against the real CSV** — never invent titles.
4. **Finalizer must only use verified Searcher output**.
5. **Enrichment is DB-first** — only reranks existing CSV candidates, never adds new titles from the web.
6. **Clarification is bounded** — max 2 turns; relaxed answers (`любое / пофиг / не важно`) stop clarifying immediately.
7. **Preference memory accumulates** — `accepted_soft_preferences`, `rejected_soft_preferences`, `external_signal_history` persist across session turns.
8. **Searcher is bounded** — use small `max_iter` and fallbacks to avoid long loops.
9. **Deterministic fallbacks are allowed** when agent output is empty or invalid.
10. **Local CLI is the primary workflow** — optimize for fast iterative runs, not container deployment.

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
  - contracts (AnalystIntent with confidence/external_signals/clarification_count)
  - runtime bootstrap
  - text normalization
  - catalog search
  - search tools
  - enrichment enricher (vibe detection, external signal detection)
  - enrichment reranking (maybe_enrich_search_output)
  - analyst-led clarification policy (no local short-circuit)
  - clarification limits (max 2 turns, relaxed-answer detection)
  - feedback preference updates (rejected preferences memory)
  - preference memory model (accepted_soft_preferences, external_signal_history)
  - association search smoke (DB-first, enrichment, external signals)
  - eval query coverage (descriptive, title, association)
  - conversation service flow (clarification + recommendation turns)
  - LLM backend routing
  - orchestration payload helpers
  - analyst fallback
  - searcher fallback
  - eval scaffolding
- Before claiming completion, always run fresh verification commands (`pytest -q`).
