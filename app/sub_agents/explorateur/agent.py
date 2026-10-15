"""Explorateur : localise et explique du code, en lecture seule."""

import os

from google.adk.agents import LlmAgent

from ...tools import outils_fichiers, outline, search
from . import prompt

explorateur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="explorateur",
    description="Localise où et comment quelque chose est implémenté dans le dépôt, en lecture seule.",
    instruction=prompt.EXPLORATEUR_PROMPT,
    tools=[search, outline, outils_fichiers()],
)
