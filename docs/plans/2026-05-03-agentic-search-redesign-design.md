# Agentic Search Redesign

Date: 2026-05-03

## Goal

Redesign the Netflix recommendation system so that:
- the 3-agent architecture is real, not simulated
- search quality is much better for descriptive queries
- Searcher becomes the main reasoning agent
- tools are simple and transparent
- the system works well with budget OpenCode Go models
- the project is local-first and no longer uses Docker

## Product direction

The system stays a 3-agent linear pipeline:
1. **Analyst** — converts the user query into structured search intent
2. **Searcher** — performs a multi-step tool-driven search loop
3. **Finalizer** — turns verified results into a friendly natural-language answer

Primary user scenario:
- descriptive recommendation requests like “что-нибудь мрачное про космос”
- exact title lookup is useful, but not the main success case

## Core architecture

### Analyst
Analyst does not search.
It outputs a strict JSON contract with:
- explicit constraints from the user
- soft preferences
- content hypotheses (topic / genre / mood)
- explanation/debug summary

Suggested contract:
- `query`
- `content_type`
- `hard_constraints`
- `soft_preferences`
- `topic_hypotheses`
- `genre_hypotheses`
- `mood_hypotheses`
- `language`
- `explanation`

### Searcher
Searcher becomes the center of the system.
It receives the Analyst intent and performs several search passes via tools.
It decides:
- which search route to try first
- which constraints are hard vs soft in practice
- when to retry
- when to relax soft constraints
- which candidates best fit the user’s meaning

Searcher should only see:
- original user query
- `AnalystIntent`
- system rules
- the most recent tool result

No full history is required in v1.

### Finalizer
Finalizer receives a verified `SearchResult` JSON and writes the user-facing answer.
It must not invent facts and must only use Searcher output.

## Search strategy

Use an **agentic search loop**.

Searcher performs multiple passes such as:
1. read intent and identify search hypotheses
2. run initial retrieval via one or two routes
3. inspect result quality
4. retry with another route or weaker soft constraints if needed
5. select the best 3–5 candidates
6. emit structured result + explanation

The primary retrieval route should support descriptive search through:
- description matching
- genre/listed_in matching
- hybrid query matching

Title search should still exist, but as one route among several.

## Search tools

Searcher should use small, explicit tools.

### 1. `search_catalog`
Low-level retrieval tool.
Supports modes such as:
- `title`
- `description`
- `listed_in`
- `cast`
- `hybrid`

Inputs:
- query text
- selected fields/mode
- hard filters
- limit

Outputs:
- candidate list
- match signals
- basic scores/features
- which fields matched

### 2. `filter_candidates`
Applies or relaxes constraints on an existing candidate set.
Useful for narrowing or broadening without restarting search.

### 3. `inspect_candidate`
Returns detailed data for one title and a compact explanation of why it matched.

### 4. `search_knowledge`
Reads the knowledge base for genre mappings, rating guidance, country aliases, mood rules, and recommendation rules.

### 5. Optional: `compare_candidate_sets`
Summarizes differences between two or more candidate pools.
Useful for search strategy, but not required in v1.

## Search backend principles

The search backend should be helpful but not “too smart”.
It should provide reliable retrieval primitives, not make strategic decisions.

Responsibilities of code:
- normalize text
- search by title / description / listed_in / cast
- apply explicit filters
- return candidates and match features

Responsibilities of the Searcher agent:
- decide which route to run
- decide when to retry
- decide how to relax soft preferences
- decide which candidates best fit the user’s intent

## Retrieval improvements

The current search is too coarse.
The new search layer should improve matching quality with:
- lowercase + punctuation cleanup
- tokenization for Cyrillic and Latin text
- normalized title matching
- exact / prefix / token-overlap / mild fuzzy title search
- better description search with weighted token overlap
- separate listed_in / genre route
- wider candidate pools for the agent to reason over

The backend should return candidate features rather than only a flat top-N list.

## Contracts

Introduce explicit Pydantic contracts between stages.

Suggested modules:
- `app/contracts/analyst.py`
- `app/contracts/search.py`
- `app/contracts/finalizer.py`

Suggested structures:
- `AnalystIntent`
- `SearchToolResult`
- `Candidate`
- `SearchTraceStep`
- `SearchResult`
- `FinalAnswerInput`

All machine-facing communication should be strict JSON.
Each contract may also include a short explanation/debug field.

## Code structure

Refactor the project into clearer layers:

- `app/contracts/` — Pydantic schemas
- `app/search/` — retrieval and candidate utilities
- `app/tools/` — CrewAI tool adapters over `app/search/`
- `app/agents/` — agent/task definitions and prompt loading
- `app/orchestration/` — pipeline wiring
- `app/evals/` — search and end-to-end evaluation

`app/main.py` should become a thin local entrypoint.
It should not contain hidden search logic, retries, or fallback strategy.

## Model strategy for OpenCode Go

The system should be designed for budget models.
This means:
- short prompts
- compact tool outputs
- strict JSON contracts
- small context windows
- limited search iterations
- no huge candidate dumps into context

### Baseline model allocation
- **Analyst**: `qwen3.5-plus`
- **Searcher**: `deepseek-v4-pro`
- **Finalizer**: `deepseek-v4-flash`

Rationale:
- Analyst needs structured extraction, not deep reasoning
- Searcher benefits most from the stronger model
- Finalizer mostly reformulates verified data

## Universal LLM client

The project should support both:
- OpenAI-compatible `/chat/completions`
- Anthropic-style `/messages`

Need a unified adapter layer so model swaps do not affect business logic.

Suggested behavior:
- one factory interface like `create_llm(role, model, temperature)`
- provider-specific transport hidden behind adapters
- model profiles such as `cheap`, `balanced`, `quality`
- role-based configuration via `.env`

This allows later evals to compare model mixes easily.

## Context window strategy

Searcher will have a limited working context.
In v1 it should include only:
- original user query
- `AnalystIntent`
- prompt/rules
- result of the most recent tool call

No multi-step search history is required initially.
If needed later, add a compact search trace summary.

## Error handling and observability

If Analyst output is weak or partial:
- Searcher starts from broad retrieval instead of failing

If a tool returns no candidates:
- Searcher retries with another route or weaker soft constraints
- if still empty, it returns explicit `no_results`

Observability should log structured operational trace data, not private reasoning:
- tool name
- arguments
- candidate counts
- retry/relaxation decisions
- final selected candidates

## Testing and evals

Testing should be split by layer:
- normalization and matching tests
- filter behavior tests
- search tool contract tests
- inter-agent contract tests
- end-to-end scenario tests

Later evals should compare:
- search quality by query type
- exact title success
- descriptive query relevance
- no-results honesty
- cost/latency across model profiles

## Local-first runtime

Docker is removed completely.
The project becomes local-first.

Main workflow:
- create and use `.venv`
- install requirements locally
- run with `python -m app.main "..."`

Project should ensure local readiness by:
- validating `.env`
- ensuring required paths exist
- creating runtime directories if missing

README and developer workflows should document only local setup.

## Non-goals for v1

- no Docker support
- no long search-history memory inside Searcher
- no overly smart monolithic search engine
- no hidden search strategy in `main.py`
- no tool that secretly performs the whole recommendation process

## Recommended implementation direction

1. define contracts
2. build local-first runtime cleanup
3. implement new search backend primitives
4. wrap them as transparent tools
5. rebuild Searcher as a real tool-driven loop
6. simplify orchestrator
7. add tests and eval scaffolding
8. compare model profiles
