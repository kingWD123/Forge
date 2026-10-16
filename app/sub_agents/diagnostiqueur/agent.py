"""Diagnostiqueur : trouve la cause commune d'échecs de tests, sans rien modifier."""

import os

from google.adk.agents import LlmAgent

from ...context.references import references
from ...context.troncature import tronquer_sorties
from ...tools import git_lecture, outils_fichiers, outline, regrouper_echecs, run_tests, search
from . import prompt
from .schema import RapportDiagnostic

diagnostiqueur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="diagnostiqueur",
    description=(
        "Trouve, en lecture seule, la cause dans le code de tests qui échouent (même très "
        "nombreux) et propose la correction. Décris le symptôme ou donne les tests concernés."
    ),
    instruction=prompt.DIAGNOSTIQUEUR_PROMPT,
    tools=[regrouper_echecs, run_tests, search, references, outline, git_lecture,
           outils_fichiers(lecture_seule=True)],
    # Réponse finale validée par ADK : les outils restent utilisables pendant le diagnostic.
    output_schema=RapportDiagnostic,
    after_tool_callback=tronquer_sorties,
)
