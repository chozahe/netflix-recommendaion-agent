import json as json_module
import re
import sys

from crewai import Agent, Crew, Process, Task

from app.agents import ANALYST_PROMPT, FINALIZER_PROMPT, SEARCHER_PROMPT
from app.config import settings
from app.knowledge.vector_store import get_knowledge_store
from app.llm.factory import create_analyst_llm, create_finalizer_llm, create_search_llm
from app.monitoring import (
    REQUESTS_TOTAL,
    REQUEST_DURATION,
    get_logger,
    setup_logging,
    setup_metrics,
)
from app.tools import KnowledgeSearchTool, NetflixSearchTool, PreferenceExtractorTool

_logger = get_logger(__name__)


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of agent text (handles stray markdown fences)."""
    # Try bare JSON first
    text = text.strip()
    if text.startswith("{"):
        return text
    # Try ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    # Fallback: find first { ... }
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0)
    return text


def _format_kb_text(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant knowledge base entries found."
    lines = ["## Relevant Knowledge Base Entries"]
    for c in chunks:
        meta = c.get("metadata", {})
        lines.append(
            f"- **{meta.get('source', '-')}** ({meta.get('section', '-')}): "
            f"{c['content'][:300]}"
        )
    return "\n".join(lines)


def run_pipeline(query: str) -> str:
    # ---- Phase 0: pre-compute all tool calls in code (no ReAct) ----
    pe = PreferenceExtractorTool()
    ns = NetflixSearchTool()
    store = get_knowledge_store()

    raw_prefs_str = pe._run(query)
    kb_chunks = store.query(query, n_results=3)
    kb_text = _format_kb_text(kb_chunks)

    # ---- Phase 1: Analyst formats preferences (no tools) ----
    analyst_llm = create_analyst_llm()
    analyst = Agent(
        role="Preference Analyst",
        goal="Extract structured content preferences from user queries in Russian or English",
        backstory=ANALYST_PROMPT,
        tools=[],
        llm=analyst_llm,
        verbose=settings.agents_verbose,
        allow_delegation=False,
    )

    analyst_task = Task(
        description=(
            f"Extract structured content preferences from this user query.\n\n"
            f"User query: {query}\n\n"
            f"The PreferenceExtractor tool was already called and returned this raw data:\n"
            f"```json\n{raw_prefs_str}\n```\n\n"
            f"{kb_text}\n\n"
            f"Use the raw PreferenceExtractor data above — it already has content_type, genre, "
            f"mood, year, country, and rating_filter extracted. Verify the genre mapping "
            f"against the Knowledge Base entries if needed. "
            f"Output ONLY a JSON object with these fields: content_type, genre, genres, mood, "
            f"moods, mood_genre_weights, year_from, year_to, country, country_aliases_matched, "
            f"rating_filter, reasoning. Do NOT call any tools — all data is already provided above."
        ),
        expected_output="A JSON object with all extracted preferences",
        agent=analyst,
    )

    crew1 = Crew(
        agents=[analyst],
        tasks=[analyst_task],
        process=Process.sequential,
        verbose=settings.agents_verbose,
    )
    _logger.info("analyst_started", query=query)
    analyst_output = crew1.kickoff()
    _logger.info("analyst_finished")
    analyst_json_str = _extract_json(str(analyst_output))

    # ---- Phase 2: parse analyst JSON, call NetflixSearch from code ----
    try:
        prefs = json_module.loads(analyst_json_str)
    except json_module.JSONDecodeError:
        _logger.warning("analyst_json_parse_failed", output=analyst_json_str[:200])
        prefs = json_module.loads(raw_prefs_str)

    rating_filter = prefs.get("rating_filter")
    rating = rating_filter[0] if rating_filter else None

    # Try search.  If zero results, degrade gracefully.
    search_result = json_module.loads(
        ns._run(
            content_type=prefs.get("content_type"),
            year_from=prefs.get("year_from"),
            year_to=prefs.get("year_to"),
            country=prefs.get("country"),
            rating=rating,
            genre=prefs.get("genre"),
            text_query=query,
            limit=10,
        )
    )

    if search_result.get("count", 0) == 0:
        yf, yt = prefs.get("year_from"), prefs.get("year_to")

        # Attempt 1: drop genre
        search_result = json_module.loads(
            ns._run(content_type=prefs.get("content_type"), year_from=yf, year_to=yt,
                    country=prefs.get("country"), rating=rating, genre=None,
                    text_query=query, limit=10)
        )

    if search_result.get("count", 0) == 0:
        yf2 = (prefs.get("year_from") or 0) - 5 if prefs.get("year_from") else None
        yt2 = (prefs.get("year_to") or 0) + 5 if prefs.get("year_to") else None
        # Attempt 2: widen year ±5
        search_result = json_module.loads(
            ns._run(content_type=prefs.get("content_type"), year_from=yf2, year_to=yt2,
                    country=prefs.get("country"), rating=rating, genre=None,
                    text_query=query, limit=10)
        )

    if search_result.get("count", 0) == 0:
        # Attempt 3: drop country
        search_result = json_module.loads(
            ns._run(content_type=prefs.get("content_type"), year_from=yf2, year_to=yt2,
                    country=None, rating=rating, genre=None,
                    text_query=query, limit=10)
        )

    if search_result.get("count", 0) == 0:
        # Attempt 4: drop rating
        search_result = json_module.loads(
            ns._run(content_type=prefs.get("content_type"), year_from=yf2, year_to=yt2,
                    country=None, rating=None, genre=None,
                    text_query=query, limit=10)
        )

    if search_result.get("count", 0) == 0:
        # Attempt 5: drop year filter entirely (text hints may point to setting ≠ release year)
        search_result = json_module.loads(
            ns._run(content_type=prefs.get("content_type"), year_from=None, year_to=None,
                    country=None, rating=None, genre=None,
                    text_query=query, limit=10)
        )

    search_json_str = json_module.dumps(search_result, ensure_ascii=False)

    # ---- Phase 3: Searcher formats results (no tools) ----
    search_llm = create_search_llm()
    searcher = Agent(
        role="Netflix Search Specialist",
        goal="Find matching movies and TV shows in the Netflix catalog using exact CSV data",
        backstory=SEARCHER_PROMPT,
        tools=[],
        llm=search_llm,
        verbose=settings.agents_verbose,
        allow_delegation=False,
    )

    searcher_task = Task(
        description=(
            f"The NetflixSearch tool was already called with the Analyst's preferences "
            f"and returned these results:\n\n"
            f"```json\n{search_json_str}\n```\n\n"
            f"Format these results into a clean JSON with count, filters_applied, "
            f"and results array. Do NOT call any tools — use the data provided above."
        ),
        expected_output="A JSON object with count, filters_applied, and results array",
        agent=searcher,
    )

    # ---- Phase 4: Finalizer writes friendly recommendations (no tools) ----
    finalizer_llm = create_finalizer_llm()
    finalizer = Agent(
        role="Recommendation Finalizer",
        goal="Craft warm, personalized recommendations from verified search results",
        backstory=FINALIZER_PROMPT,
        tools=[],
        llm=finalizer_llm,
        verbose=settings.agents_verbose,
        allow_delegation=False,
    )

    finalizer_task = Task(
        description=(
            f"The search for '{query}' returned these results:\n\n"
            f"```json\n{search_json_str}\n```\n\n"
            f"Write a friendly, warm recommendation message for the user. "
            f"Pick 3–5 titles, include title/type/year, a short description, "
            f"and why each fits the query. Respond in the user's language. "
            f"No markdown tables or bullet lists. Do NOT invent facts."
        ),
        expected_output="A conversational recommendation message in natural language",
        agent=finalizer,
    )

    crew2 = Crew(
        agents=[searcher, finalizer],
        tasks=[searcher_task, finalizer_task],
        process=Process.sequential,
        verbose=settings.agents_verbose,
    )
    _logger.info("searcher_finalizer_started")
    result = crew2.kickoff()
    _logger.info("searcher_finalizer_finished")
    return str(result)


def main() -> None:
    setup_logging(settings.log_file)
    setup_metrics(settings.metrics_port)
    _logger.info("system_started", metrics_port=settings.metrics_port)

    if not settings.openai_api_key:
        _logger.error("no_api_key")
        print("ERROR: OPENAI_API_KEY is not set. Create a .env file with your key.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python -m app.main 'Your Netflix query here'")
        print("Example: python -m app.main \"хочу фильм про космос\"")
        sys.exit(0)

    query = " ".join(sys.argv[1:])
    _logger.info("request_received", query=query)

    try:
        with REQUEST_DURATION.time():
            result = run_pipeline(query)

        REQUESTS_TOTAL.labels(status="success").inc()
        _logger.info("request_completed", query=query)

        print()
        print(result)
    except Exception as exc:
        REQUESTS_TOTAL.labels(status="error").inc()
        _logger.error("request_failed", query=query, error=str(exc))
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
