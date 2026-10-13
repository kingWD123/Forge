"""Évaluateur de délégation : décide si une tâche tient dans le contexte courant."""

import os

from google.adk.agents import LlmAgent

from . import prompt

evaluateur_agent = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="evaluateur_agent",
    description="Décide si une tâche doit être déléguée à un sous-agent.",
    instruction=prompt.EVALUATEUR_PROMPT,
)
