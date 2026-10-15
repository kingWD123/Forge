"""Rédacteur de tests : écrit des tests, uniquement dans tests/."""

import os

from google.adk.agents import LlmAgent

from ...permissions import autoriser
from ...tools import edit_file, outils_fichiers, outline, run_tests
from . import prompt

redacteur_tests = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="redacteur_tests",
    description="Écrit des tests pytest pour un comportement ou un module, uniquement dans tests/.",
    instruction=prompt.REDACTEUR_TESTS_PROMPT,
    tools=[outline, edit_file, run_tests, outils_fichiers()],
    before_tool_callback=autoriser,
)
