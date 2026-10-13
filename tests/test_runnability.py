"""Vérifie que l'application, l'agent racine, ses outils et ses sous-agents se chargent."""

import asyncio


def test_root_agent_loads():
    from app.agent import root_agent

    assert root_agent.name == "atelier"
    tools = asyncio.run(root_agent.canonical_tools())
    assert {t.name for t in tools} == {
        "ReadFile",
        "WriteFile",
        "Execute",
        "search",
        "edit_file",
        "run_tests",
        "evaluateur_agent",
        "forgeron_agent",
        "banc_essai_agent",
        "verificateur_agent",
    }


def test_app_avec_reflect_and_retry():
    from app.agent import app, root_agent

    assert app.root_agent is root_agent
    assert [type(p).__name__ for p in app.plugins] == ["ReflectAndRetryToolPlugin"]
