"""Explorateur : localise et explique du code, en lecture seule."""

import os

from google.adk.agents import LlmAgent

from ...context.references import references
from ...context.troncature import tronquer_sorties
from ...tools import git_lecture, list_files, outil_inconnu, outils_fichiers, outline, search
from . import prompt
from .schema import RapportExploration

explorateur = LlmAgent(
    # EXPLORATEUR_MODEL permet d'essayer un modèle plus rapide et moins cher pour l'exploration.
    model=os.getenv("EXPLORATEUR_MODEL") or os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="explorateur",
    description=(
        "QUAND : avant de modifier du code que tu ne connais pas, si trouver le bon endroit demande "
        "plusieurs recherches et lectures. QUOI : explore en lecture seule et rend une réponse courte "
        "(où est le code, comment il marche, qui l'utilise, conventions du projet). DONNE-LUI : une "
        "question précise, et la profondeur : rapide (localiser) ou approfondie (inventaire complet)."
    ),
    instruction=prompt.EXPLORATEUR_PROMPT,
    tools=[search, references, list_files, outline, git_lecture, outils_fichiers(lecture_seule=True), outil_inconnu],
    # Réponse finale validée par ADK : les outils restent utilisables pendant l'exploration.
    output_schema=RapportExploration,
    after_tool_callback=tronquer_sorties,
)
