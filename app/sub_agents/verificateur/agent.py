"""Vérificateur : relance les tests, vérifie les contraintes épinglées et relit le diff."""

import os

from google.adk.agents import LlmAgent

from . import prompt

verificateur_agent = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="verificateur_agent",
    description="Vérifie tests, contraintes épinglées et diff avant de proposer une modification.",
    instruction=prompt.VERIFICATEUR_PROMPT,
)
