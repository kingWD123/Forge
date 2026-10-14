"""Coupe des sorties d'outils trop longues (after_tool_callback).

- Execute : on garde le DÉBUT et la FIN, on retire le milieu. Dans une trace d'erreur
  ou une sortie de commande, la cause est souvent en bas : la coupe d'ADK, qui ne
  garde que le début, la perdait.
- ReadFile : on garde le début, et on indique à quelle ligne reprendre la lecture.

S'applique dans toutes les configurations : c'est la qualité des outils, pas le Compilateur.
"""

import re
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

LIMITE = 8_000   # caractères par sortie, environ 200 lignes


def couper_debut_et_fin(texte: str, limite: int = LIMITE) -> str:
    if len(texte) <= limite:
        return texte
    moitie = limite // 2
    lignes_retirees = texte[moitie:-moitie].count("\n")
    return (f"{texte[:moitie]}\n… [{lignes_retirees} lignes retirées au milieu : sortie trop longue] …\n"
            f"{texte[-moitie:]}")


def couper_lecture(contenu: str, limite: int = LIMITE) -> str:
    """Garde les premières lignes complètes ; ReadFile numérote ses lignes ("   42\\t...")."""
    if len(contenu) <= limite:
        return contenu
    debut = contenu[:limite].rsplit("\n", 1)[0]
    numero = re.match(r"\s*(\d+)\t", debut.rsplit("\n", 1)[-1])
    suite = f" Lis la suite avec start_line={int(numero.group(1)) + 1}." if numero else ""
    return f"{debut}\n… [lecture coupée à {limite} caractères.{suite}]"


def tronquer_sorties(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext,
                     tool_response: Any) -> dict | None:
    """after_tool_callback : None garde la réponse telle quelle, un dict la remplace."""
    if not isinstance(tool_response, dict):
        return None
    reponse = dict(tool_response)
    if tool.name == "Execute":
        for cle in ("stdout", "stderr"):
            if isinstance(reponse.get(cle), str):
                reponse[cle] = couper_debut_et_fin(reponse[cle])
    elif tool.name == "ReadFile" and isinstance(reponse.get("content"), str):
        reponse["content"] = couper_lecture(reponse["content"])
    else:
        return None
    return reponse if reponse != tool_response else None
