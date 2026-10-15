"""Migrateur : applique une règle de transformation à un fichier par appel."""

import os

from google.adk.agents import LlmAgent

from ...permissions import autoriser
from ...tools import edit_file, outils_fichiers, outline, run_tests
from . import prompt

migrateur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="migrateur",
    description="Applique une règle de transformation à UN fichier par appel (à appeler une fois par fichier).",
    instruction=prompt.MIGRATEUR_PROMPT,
    tools=[outline, edit_file, run_tests, outils_fichiers()],
    before_tool_callback=autoriser,
)
