from __future__ import annotations

import json as json_module
import re

from crewai import Crew, Process, Task

from app.agents.definitions import (
    build_analyst_agent,
    build_finalizer_agent,
    build_searcher_agent,
)
from app.contracts.analyst import AnalystIntent
from app.contracts.search import Candidate, SearchResult
from app.monitoring import get_logger
from app.search.enricher import enrich_shortlisted_titles
from app.tools.netflix_search import NetflixSearchTool

_logger = get_logger(__name__)



def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("{"):
        return text
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text



def build_fallback_intent(query: str) -> AnalystIntent:
    return AnalystIntent(
        query=query,
        content_type=None,
        hard_constraints={},
        soft_preferences={},
        topic_hypotheses=[],
        genre_hypotheses=[],
        mood_hypotheses=[],
        language="ru" if re.search(r"[А-Яа-я]", query) else "en",
        explanation="Analyst failed — passing raw query to Searcher with minimal intent",
    )



def build_fallback_search_result(intent: AnalystIntent) -> SearchResult:
    tool = NetflixSearchTool()
    hard = intent.hard_constraints or {}
    payload = json_module.loads(
        tool._run(
            content_type=intent.content_type,
            year_from=hard.get("year_from"),
            year_to=hard.get("year_to"),
            country=hard.get("country"),
            rating=hard.get("rating"),
            text_query=intent.query,
            mode="title" if len(intent.query.split()) <= 2 else "hybrid",
            limit=10,
        )
    )
    candidates = [Candidate.model_validate(row) for row in payload.get("results", [])]
    if not candidates:
        return SearchResult(
            status="no_results",
            selected=[],
            discarded=[],
            explanation="Fallback search found no verified catalog matches.",
        )
    return SearchResult(
        status="ok",
        selected=candidates[:5],
        discarded=candidates[5:],
        explanation="Fallback search selected verified candidates from NetflixSearch.",
    )



def build_searcher_input(intent: AnalystIntent, last_tool_result: dict) -> dict:
    return {
        "query": intent.query,
        "intent": intent.model_dump(),
        "last_tool_result": last_tool_result,
    }



def run_analyst(query: str) -> AnalystIntent:
    analyst = build_analyst_agent()
    analyst_task = Task(
        description=(
            f"User query: {query}\n\n"
            "Return ONLY strict JSON for the search intent with these fields: "
            "query, content_type, hard_constraints, soft_preferences, topic_hypotheses, "
            "genre_hypotheses, mood_hypotheses, language, explanation, "
            "needs_clarification, clarification_question, missing_slots, "
            "confidence, external_signals, clarification_count."
        ),
        expected_output="A strict JSON object matching the AnalystIntent contract.",
        agent=analyst,
    )
    crew = Crew(agents=[analyst], tasks=[analyst_task], process=Process.sequential)
    _logger.info("analyst_started", query=query)
    try:
        analyst_output = str(crew.kickoff())
        _logger.info("analyst_finished")
        analyst_json = _extract_json(analyst_output)
        return AnalystIntent.model_validate(json_module.loads(analyst_json))
    except Exception as exc:
        _logger.warning("analyst_fallback_used", query=query, error=str(exc))
        return build_fallback_intent(query)



def maybe_enrich_search_output(intent: AnalystIntent, search_output: str) -> dict:
    try:
        payload = json_module.loads(search_output)
    except json_module.JSONDecodeError:
        return {"selected": [], "discarded": [], "status": "invalid", "enrichment_used": False}

    selected = payload.get("selected", [])
    if not isinstance(selected, list) or not selected:
        payload["enrichment_used"] = False
        return payload

    titles = [item.get("title") for item in selected if isinstance(item, dict) and item.get("title")]
    enrichment = enrich_shortlisted_titles(
        intent.query,
        titles,
        external_signals=intent.external_signals,
    )
    if not enrichment:
        payload["enrichment_used"] = False
        return payload

    enrichment_by_title = {item.get("title"): item for item in enrichment if item.get("title")}
    has_positive_match = any(
        int(item.get("confidence_boost", 0)) > 0 or item.get("matched_external_signals")
        for item in enrichment_by_title.values()
    )
    if not has_positive_match:
        payload["enrichment_used"] = False
        return payload

    def _score(item: dict) -> int:
        enriched = enrichment_by_title.get(item.get("title"), {})
        return int(enriched.get("confidence_boost", 0))

    reranked = sorted(selected, key=_score, reverse=True)
    for item in reranked:
        enriched = enrichment_by_title.get(item.get("title"))
        if enriched:
            item["matched_external_signals"] = enriched.get("matched_external_signals", [])
            item["confidence_boost"] = enriched.get("confidence_boost", 0)
            item["enrichment_evidence"] = enriched.get("evidence", [])

    payload["selected"] = reranked
    payload["enrichment_used"] = True
    return payload



def run_searcher(intent: AnalystIntent, last_tool_result: dict | None = None) -> str:
    searcher = build_searcher_agent()
    searcher_input = build_searcher_input(intent=intent, last_tool_result=last_tool_result or {})
    searcher_task = Task(
        description=(
            "You are given the original query and Analyst intent below.\n\n"
            f"{json_module.dumps(searcher_input, ensure_ascii=False, indent=2)}\n\n"
            "Perform a tool-driven search loop. Start with NetflixSearch in mode='hybrid' or "
            "mode='description' for descriptive requests. Use hard constraints from intent when present. "
            "If results are weak, retry with another route or relax soft preferences. Optionally inspect "
            "top candidates. Output ONLY JSON with fields: status, selected, discarded, explanation."
        ),
        expected_output="A strict JSON object matching the SearchResult contract.",
        agent=searcher,
    )
    search_crew = Crew(agents=[searcher], tasks=[searcher_task], process=Process.sequential)
    _logger.info("searcher_started", query=intent.query)
    try:
        search_output = str(search_crew.kickoff())
        _logger.info("searcher_finished")
        return search_output
    except Exception as exc:
        _logger.warning("searcher_fallback_used", query=intent.query, error=str(exc))
        return build_fallback_search_result(intent).model_dump_json(ensure_ascii=False)



def run_finalizer(query: str, intent: AnalystIntent, search_output: str) -> str:
    finalizer = build_finalizer_agent()
    finalizer_task = Task(
        description=(
            f"Original user query: {query}\n\n"
            f"Analyst intent explanation: {intent.explanation}\n\n"
            f"Searcher output:\n{search_output}\n\n"
            "Write a friendly final recommendation in the user's language. Do not invent facts."
        ),
        expected_output="A conversational recommendation message in natural language.",
        agent=finalizer,
    )
    final_crew = Crew(agents=[finalizer], tasks=[finalizer_task], process=Process.sequential)
    _logger.info("finalizer_started", query=query)
    result = str(final_crew.kickoff())
    _logger.info("finalizer_finished")
    return result



def run_pipeline(query: str) -> str:
    intent = run_analyst(query)
    if intent.needs_clarification:
        return intent.clarification_question or "Please clarify your request."
    search_output = run_searcher(intent=intent, last_tool_result={})
    enriched_output = maybe_enrich_search_output(intent, search_output)
    return run_finalizer(
        query=query,
        intent=intent,
        search_output=json_module.dumps(enriched_output, ensure_ascii=False),
    )
