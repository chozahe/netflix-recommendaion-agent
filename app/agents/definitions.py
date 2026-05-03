from crewai import Agent

from app.agents import ANALYST_PROMPT, FINALIZER_PROMPT, SEARCHER_PROMPT
from app.config import settings
from app.llm.factory import create_analyst_llm, create_finalizer_llm, create_search_llm
from app.tools import (
    FilterCandidatesTool,
    InspectCandidateTool,
    NetflixSearchTool,
    PosterLookupTool,
)


def build_analyst_agent() -> Agent:
    return Agent(
        role="Preference Analyst",
        goal="Extract structured search intent from user queries in Russian or English",
        backstory=ANALYST_PROMPT,
        tools=[],
        llm=create_analyst_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
        max_iter=settings.analyst_max_iter,
    )



def build_searcher_agent() -> Agent:
    return Agent(
        role="Netflix Search Specialist",
        goal="Use transparent search tools to find verified Netflix titles for the user intent",
        backstory=SEARCHER_PROMPT,
        tools=[
            NetflixSearchTool(),
            FilterCandidatesTool(),
            InspectCandidateTool(),
        ],
        llm=create_search_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
        max_iter=settings.searcher_max_iter,
    )



def build_finalizer_agent() -> Agent:
    return Agent(
        role="Recommendation Finalizer",
        goal="Craft warm, personalized recommendations from verified search results",
        backstory=FINALIZER_PROMPT,
        tools=[PosterLookupTool()],
        llm=create_finalizer_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
        max_iter=settings.finalizer_max_iter,
    )
