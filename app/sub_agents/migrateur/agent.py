"""Migrateur : applique une règle de transformation à un fichier par appel."""

import os
import re
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ...context.troncature import tronquer_sorties
from ...permissions import autoriser
from ...prompt import FRONTIERE_DES_PREUVES
from ...tools import edit_file, outil_inconnu, outils_fichiers, outline, search
from . import prompt
from .schema import RapportMigration
from ..rapport import rapport_par_set_model_response


def limiter_au_fichier_confie(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """Le migrateur ne peut modifier que le fichier cité dans la demande qu'il a reçue."""
    if tool.name != "edit_file":
        return None
    demande = " ".join(p.text or "" for p in (tool_context.user_content.parts or [])) \
        if tool_context.user_content else ""
    fichiers_cites = {m.replace("\\", "/") for m in re.findall(r"[\w./\\-]+\.\w+", demande)}
    chemin = str(args.get("path", "")).replace("\\", "/").removeprefix("./")
    if chemin not in fichiers_cites:
        return {"status": "error",
                "error": f"Tu ne peux modifier que le fichier qui t'a été confié, pas {chemin}."}
    return autoriser(tool, args, tool_context)


migrateur = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="migrateur",
    description=(
        "QUAND : seulement pour appliquer une règle à UN fichier précis ; pour une migration dans "
        "plusieurs fichiers, appelle migrer_partout. QUOI : applique la règle (renommage, API "
        "remplacée...) à toutes les occurrences du fichier, chaînes et commentaires compris. "
        "DONNE-LUI : le chemin du fichier, la règle et un exemple."
    ),
    instruction=prompt.MIGRATEUR_PROMPT + FRONTIERE_DES_PREUVES,
    tools=[search, outline, edit_file, outils_fichiers(lecture_seule=True), outil_inconnu],
    # Il ne modifie que le fichier confié ; les autorisations habituelles s'appliquent ensuite.
    before_tool_callback=limiter_au_fichier_confie,
    output_schema=RapportMigration,
    after_tool_callback=tronquer_sorties,
    # Rapport rendu en texte : repassé par set_model_response, où le schéma est validé.
    after_model_callback=rapport_par_set_model_response,
)
