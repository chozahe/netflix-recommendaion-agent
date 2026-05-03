from crewai import Agent

from app.agents import ANALYST_PROMPT, FINALIZER_PROMPT, SEARCHER_PROMPT
from app.config import settings
from app.llm.factory import create_analyst_llm, create_finalizer_llm, create_search_llm
from app.tools import (
    FilterCandidatesTool,
    InspectCandidateTool,
    KnowledgeSearchTool,
    NetflixSearchTool,
    PreferenceExtractorTool,
)


def build_analyst_agent() -> Agent:
    return Agent(
        role="Preference Analyst",
        goal="Extract structured search intent from user queries in Russian or English",
        backstory=ANALYST_PROMPT,
        tools=[PreferenceExtractorTool(), KnowledgeSearchTool()],
        llm=create_analyst_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
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
            KnowledgeSearchTool(),
        ],
        llm=create_search_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
    )



def build_finalizer_agent() -> Agent:
    return Agent(
        role="Recommendation Finalizer",
        goal="Craft warm, personalized recommendations from verified search results",
        backstory=FINALIZER_PROMPT,
        tools=[],
        llm=create_finalizer_llm(),
        verbose=settings.agents_verbose,
        allow_delegation=False,
    )
