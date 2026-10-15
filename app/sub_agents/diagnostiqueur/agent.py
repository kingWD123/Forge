"""Diagnostiqueur : trouve la cause commune d'échecs de tests, sans rien modifier."""

import os

from google.adk.agents import LlmAgent

from ...tools import outils_fichiers, outline, run_tests, search
from . import prompt

diagnostiqueur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="diagnostiqueur",
    description="Trouve la cause commune de tests en échec et propose la correction, sans rien modifier.",
    instruction=prompt.DIAGNOSTIQUEUR_PROMPT,
    tools=[run_tests, search, outline, outils_fichiers()],
)
