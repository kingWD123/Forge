"""Banc d'essai : boucle essai -> diagnostic, 3 essais maximum."""

import os

from google.adk.agents import LlmAgent, LoopAgent

from . import prompt

testeur_agent = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="testeur_agent",
    description="Lance un sous-agent forgé dans un worktree isolé et juge le résultat par les tests.",
    instruction=prompt.TESTEUR_PROMPT,
)

banc_essai_agent = LoopAgent(
    name="banc_essai_agent",
    description="Teste un sous-agent forgé dans un git worktree isolé, 3 essais maximum.",
    sub_agents=[testeur_agent],
    max_iterations=3,
)
