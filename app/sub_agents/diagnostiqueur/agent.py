"""Diagnostiqueur : trouve la cause commune d'échecs de tests, sans rien modifier."""

import os

from google.adk.agents import LlmAgent

from ...context.references import references
from ...context.troncature import tronquer_sorties
from ...prompt import FRONTIERE_DES_PREUVES
from ...tools import experimenter, git_lecture, outil_inconnu, outils_fichiers, outline, regrouper_echecs, run_tests, search
from . import prompt
from .schema import RapportDiagnostic
from ..rapport import rapport_par_set_model_response

diagnostiqueur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="diagnostiqueur",
    description=(
        "QUAND : EN PREMIER, avant toute modification, dès que plus de 5 tests échouent, ou "
        "qu'un échec reste incompris après une lecture. QUOI : trouve la cause dans le code "
        "source (même avec des centaines d'échecs) en reproduisant l'échec sur un cas minimal, sans "
        "rien modifier, et propose la correction, que tu "
        "appliques ensuite. DONNE-LUI : le symptôme et quelques tests en échec."
    ),
    instruction=prompt.DIAGNOSTIQUEUR_PROMPT + FRONTIERE_DES_PREUVES,
    tools=[regrouper_echecs, run_tests, experimenter, search, references, outline, git_lecture, outil_inconnu,
           outils_fichiers(lecture_seule=True)],
    # Réponse finale validée par ADK : les outils restent utilisables pendant le diagnostic.
    output_schema=RapportDiagnostic,
    after_tool_callback=tronquer_sorties,
    # Rapport rendu en texte : repassé par set_model_response, où le schéma est validé.
    after_model_callback=rapport_par_set_model_response,
)
