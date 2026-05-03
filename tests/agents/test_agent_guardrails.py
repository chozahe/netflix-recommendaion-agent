from app.agents.definitions import build_analyst_agent, build_finalizer_agent, build_searcher_agent


def test_searcher_agent_has_low_iteration_limit():
    agent = build_searcher_agent()
    assert agent.max_iter == 3


def test_other_agents_have_small_iteration_limits():
    assert build_analyst_agent().max_iter == 2
    assert build_finalizer_agent().max_iter == 2
