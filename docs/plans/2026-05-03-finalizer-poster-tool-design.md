# Finalizer Poster Tool Design

Date: 2026-05-03
Branch: `feat/finalizer-poster-tool`
Status: validated design

## Goal

Add poster lookup as a narrow tool for the Finalizer only.

The system should:
- keep **Analyst** unchanged
- keep **Searcher** focused on verified catalog retrieval only
- let **Finalizer** optionally fetch a poster URL for already verified titles
- return recommendations even when poster lookup fails
- expose poster URLs through the API and support CLI rendering with fallback

## Why this design

The current DuckDuckGo-based web search is not a good fit for Analyst or Searcher in this use case. Those agents should stay focused on intent analysis and catalog retrieval. Poster lookup is presentation-layer enrichment, so the cleanest place for it is the Finalizer.

A narrow tool is preferred over a general web search tool because it preserves architectural boundaries:
- no new title discovery from the web
- no extra factual enrichment from the web
- no agent freedom to search unrelated content
- easy best-effort behavior and easier tests

## Chosen approach

Use a **`PosterLookupTool`** attached only to the Finalizer.

Behavior:
- input: a verified title, plus optional metadata such as `content_type` and `release_year`
- implementation: run DuckDuckGo image search
- output: a single `poster_url` or `null`
- scope: only for titles already returned by Searcher
- failure mode: silent fallback to `null`, never fail the recommendation flow

## Architecture

Pipeline responsibility remains:
- **Analyst** → produce structured intent
- **Searcher** → retrieve verified Netflix titles from CSV/tools
- **Finalizer** → produce user-facing answer and optionally attach poster URLs

Poster lookup moves out of retrieval/enrichment logic and becomes a final presentation step.

Recommended flow:
1. Searcher returns verified candidates.
2. Finalizer formats recommendations.
3. Finalizer calls `PosterLookupTool` for selected verified titles.
4. Tool returns `poster_url | null`.
5. API response includes `poster_url` inside each recommendation.
6. CLI tries to render inline image; if rendering fails, it prints the URL.

## Components to add or change

### 1. `PosterLookupTool`

Add a new tool in `app/tools/poster_lookup.py`.

Responsibilities:
- accept a narrow structured input
- build a safe image-search query from verified title metadata
- call DuckDuckGo image search
- rank a small set of returned images
- return one best `poster_url` or `null`

This should not expose arbitrary free-form browsing behavior to the Finalizer.

### 2. Image search adapter

Add a dedicated low-level image search adapter, ideally separate from the current text-enrichment search logic.

Suggested options:
- new file: `app/search/image_search.py`, or
- extend `app/search/web_search.py` carefully without mixing unrelated responsibilities

The preferred design is a separate adapter because poster lookup and text enrichment are different use cases.

### 3. Finalizer agent

Update `build_finalizer_agent()` to include `PosterLookupTool`.

The Finalizer prompt should explicitly state:
- use the tool only for titles already verified by Searcher
- do not search for new titles
- do not add new external facts
- use the tool only to attach poster URLs
- if no poster is found, continue without it

### 4. Contracts and API

Extend recommendation storage/response shape with:
- `poster_url: str | None = None`

Recommended place:
- `StoredRecommendation`

This keeps API changes minimal and backward-compatible for clients that ignore the new field.

### 5. CLI behavior

Current CLI prints only the message text. It should be extended to also inspect returned recommendations.

Desired behavior:
- print the normal recommendation message
- for each recommendation, if `poster_url` exists, try inline rendering in Ghostty
- if inline rendering is unavailable or fails, print the URL as fallback

CLI image rendering should be isolated behind a small helper rather than mixed directly into the chat loop.

## DuckDuckGo usage

DuckDuckGo can be used for image search through the Python package already referenced in the project.

Expected search primitive:
- `DDGS().images(...)`

Important caveats:
- results may include posters, screenshots, fan art, collages, or irrelevant media
- URLs may be unstable or third-party hosted
- rate limits or empty results may occur
- image search should therefore be treated as best-effort only

Because of this, the tool must include local ranking/filtering logic and return `null` when confidence is weak.

## Query strategy

The tool should build deterministic queries rather than letting the LLM invent arbitrary searches.

Example query patterns:
- `"<title>" poster netflix`
- `"<title>" official poster movie`
- `"<title>" official poster series`

Optional metadata can improve precision:
- release year
- content type (`Movie` / `TV Show`)

The tool should use only a small number of image results per title.

## Ranking strategy

Image ranking should be deterministic local code, not another LLM step.

Possible positive signals:
- result title/url contains the exact title
- contains words like `poster`, `official`, `movie`, `series`
- sufficiently large image dimensions
- trusted-looking sources

Possible negative signals:
- `fanart`
- `review`
- `recap`
- `ending explained`
- `soundtrack`
- `episode`
- `meme`
- unrelated title mismatch

Output rule:
- choose one best image URL if confidence is acceptable
- otherwise return `null`

## Data flow

Structured flow:
1. User asks for recommendations.
2. Analyst produces `AnalystIntent`.
3. Searcher returns verified search output from catalog tools.
4. Finalizer prepares user-facing recommendations.
5. For selected verified titles, Finalizer calls `PosterLookupTool`.
6. Tool returns `poster_url` values.
7. Final API response includes text plus recommendations with poster URLs.
8. CLI renders inline image if possible, otherwise prints the URL.

## Error handling

Poster lookup must never break the main recommendation flow.

Failure cases:
- DDG dependency unavailable
- request timeout
- rate limit
- empty image results
- low-confidence match
- invalid URL
- CLI render failure

Required behavior:
- log internally where useful
- return `null` for the poster
- still return the recommendation successfully
- CLI falls back to text URL output

## Limits and guardrails

To preserve fast local UX:
- restrict lookup to top-N recommendations only
- use a short timeout
- use a small `max_results`
- avoid repeated retries
- return only one `poster_url` per title
- never use the tool for new-title discovery
- never let poster search modify ranking of recommendations

Poster lookup is presentation enrichment only, not search relevance logic.

## Testing strategy

Add tests for:

### Unit tests
- query construction for poster lookup
- local ranking behavior for image results
- negative filtering of noisy/fan-art-like results
- best-effort `null` fallback on exceptions/timeouts

### Tool tests
- `PosterLookupTool` returns expected `poster_url`
- tool never returns new titles
- tool handles empty DDG image results safely

### Contract/API tests
- `poster_url` serializes through recommendation responses
- API remains valid when `poster_url` is `null`

### CLI tests
- normal text output still works
- fallback URL output works when rendering is not available
- inline rendering helper failure does not crash chat

### Regression tests
- recommendation flow still works when poster lookup is disabled or broken
- Finalizer still respects verified Searcher output only

## Non-goals

This design intentionally does not include:
- moving web search into Analyst
- moving web search into Searcher for title retrieval
- using web results to invent or verify new factual metadata
- multi-image galleries
- external image databases requiring API keys
- blocking response generation on poster success

## Recommended implementation order

1. Add failing tests for poster lookup ranking and fallback behavior.
2. Add image-search adapter and `PosterLookupTool`.
3. Attach the tool to Finalizer and tighten Finalizer prompt.
4. Extend contracts with `poster_url`.
5. Extend API/CLI output handling.
6. Add CLI inline-image helper with URL fallback.
7. Run full regression tests.

## Summary

The chosen design keeps the core architecture intact:
- Search stays deterministic and catalog-first.
- Finalizer gets a narrow presentation-layer tool.
- DuckDuckGo image search is used only as best-effort poster lookup.
- API gains simple `poster_url` support.
- CLI can render images inline in Ghostty with safe fallback behavior.
