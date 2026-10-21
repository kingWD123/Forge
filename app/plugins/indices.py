"""Plugin IndicesCibles : ajoute un indice à la sortie d'un outil quand une situation connue
se présente, au moment exact où l'Atelier la voit.

Une consigne écrite dans le prompt peut ne pas être suivie ; un plugin agit dans la boucle
d'outils et ne coûte rien tant qu'il ne se déclenche pas (Harness² : « ajouter un indice
ciblé après une signature qui revient »). Deux situations, observées dans nos essais :

- run_tests montre plus de SEUIL_ECHECS échecs et le diagnostiqueur n'a pas encore été
  appelé -> indice : appelle-le avant de modifier quoi que ce soit ;
- search trouve le motif dans plus de SEUIL_FICHIERS fichiers, la consigne demande une
  migration, et migrer_partout n'a pas encore été appelé -> indice : charge la skill migration.

Un indice n'est donné que si l'outil conseillé est disponible pour cet agent : en
configurations A et B (sans spécialistes), le plugin ne fait rien.
"""

import re
from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from app.consigne import DEMANDE_DE_MIGRATION, demande

SEUIL_ECHECS = 5
SEUIL_FICHIERS = 2


class IndicesCibles(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="indices_cibles")

    async def after_tool_callback(self, *, tool: BaseTool, tool_args: dict[str, Any],
                                  tool_context: ToolContext, result: Any) -> Optional[dict]:
        if not isinstance(result, dict):
            return None
        indice = indice_pour(tool.name, result, tool_context)
        return {**result, "indice": indice} if indice else None


def indice_pour(outil: str, resultat: dict, tool_context: ToolContext) -> str:
    """L'indice à ajouter à la sortie de cet outil, ou '' si aucun."""
    disponibles = outils_de_l_agent(tool_context)
    deja_appeles = outils_deja_appeles(tool_context)

    if outil == "run_tests" and "diagnostiqueur" in disponibles and "diagnostiqueur" not in deja_appeles:
        echecs = resultat.get("counts", {}).get("failed", 0) + resultat.get("counts", {}).get("errors", 0)
        if echecs > SEUIL_ECHECS:
            return (f"{echecs} tests échouent : appelle le diagnostiqueur AVANT de modifier quoi que "
                    "ce soit. Il trouve la cause commune ; tu appliqueras ensuite sa correction.")

    if outil == "search" and "migrer_partout" in disponibles and "migrer_partout" not in deja_appeles:
        fichiers = {m.split(":", 1)[0] for m in resultat.get("matches", [])}
        if len(fichiers) > SEUIL_FICHIERS and demande(DEMANDE_DE_MIGRATION, tool_context):
            return (f"Ce motif apparaît dans {len(fichiers)} fichiers et la consigne demande une "
                    "migration : charge la skill `migration` plutôt que de modifier ces fichiers toi-même.")
    return ""


def outils_de_l_agent(tool_context: ToolContext) -> set[str]:
    agent = tool_context._invocation_context.agent
    return {getattr(t, "name", None) or getattr(t, "__name__", "") for t in getattr(agent, "tools", [])}


def outils_deja_appeles(tool_context: ToolContext) -> set[str]:
    evenements = getattr(getattr(tool_context, "session", None), "events", None) or []
    return {appel.name for e in evenements for appel in e.get_function_calls()}
