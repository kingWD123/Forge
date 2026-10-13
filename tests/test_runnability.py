"""Vérifie que l'agent racine, ses outils et ses sous-agents se chargent."""

import asyncio


def test_root_agent_loads():
    from app.agent import root_agent

    assert root_agent.name == "atelier"
    tools = asyncio.run(root_agent.canonical_tools())
    assert {t.name for t in tools} == {
        "ReadFile",
        "EditFile",
        "WriteFile",
        "Execute",
        "search",
        "run_tests",
        "evaluateur_agent",
        "forgeron_agent",
        "banc_essai_agent",
        "verificateur_agent",
    }
