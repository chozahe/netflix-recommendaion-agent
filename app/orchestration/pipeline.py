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
from app.monitoring import get_logger

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



def build_searcher_input(intent: AnalystIntent, last_tool_result: dict) -> dict:
    return {
        "query": intent.query,
        "intent": intent.model_dump(),
        "last_tool_result": last_tool_result,
    }



def run_pipeline(query: str) -> str:
    analyst = build_analyst_agent()
    searcher = build_searcher_agent()
    finalizer = build_finalizer_agent()

    analyst_task = Task(
        description=(
            f"User query: {query}\n\n"
            "Use PreferenceExtractor first. Use KnowledgeSearch only if needed. "
            "Return ONLY strict JSON for the search intent with these fields: "
            "query, content_type, hard_constraints, soft_preferences, topic_hypotheses, "
            "genre_hypotheses, mood_hypotheses, language, explanation."
        ),
        expected_output="A strict JSON object matching the AnalystIntent contract.",
        agent=analyst,
    )

    crew1 = Crew(
        agents=[analyst],
        tasks=[analyst_task],
        process=Process.sequential,
    )
    _logger.info("analyst_started", query=query)
    analyst_output = str(crew1.kickoff())
    _logger.info("analyst_finished")

    analyst_json = _extract_json(analyst_output)
    try:
        intent = AnalystIntent.model_validate(json_module.loads(analyst_json))
    except Exception:
        _logger.warning("analyst_contract_parse_failed", output=analyst_json[:300])
        intent = AnalystIntent(
            query=query,
            content_type=None,
            hard_constraints={},
            soft_preferences={},
            topic_hypotheses=[],
            genre_hypotheses=[],
            mood_hypotheses=[],
            language="ru" if re.search(r"[А-Яа-я]", query) else "en",
            explanation="Fallback intent due to parse failure",
        )

    searcher_input = build_searcher_input(intent=intent, last_tool_result={})
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

    search_crew = Crew(
        agents=[searcher],
        tasks=[searcher_task],
        process=Process.sequential,
    )
    _logger.info("searcher_started", query=query)
    search_output = str(search_crew.kickoff())
    _logger.info("searcher_finished")

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
    final_crew = Crew(
        agents=[finalizer],
        tasks=[finalizer_task],
        process=Process.sequential,
    )
    _logger.info("finalizer_started", query=query)
    result = str(final_crew.kickoff())
    _logger.info("finalizer_finished")
    return result
