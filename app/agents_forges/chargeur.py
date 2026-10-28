"""Chargeur maison : une fiche validée devient un LlmAgent.

Chaque nom d'outil de la fiche correspond à un outil de l'Atelier, chaque skill à un dossier
du catalogue (app/skills, .forge/skills) ; le périmètre (scope) est
imposé par un before_tool_callback, puis les autorisations habituelles s'appliquent.
"""

import fnmatch
from pathlib import Path
from typing import Any, Literal

from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.skill_toolset import SkillDiscoveryMode, SkillToolset
from google.adk.tools.tool_context import ToolContext
from pydantic import BaseModel, Field

from ..context.troncature import tronquer_sorties
from ..permissions import WRITE_TOOLS, autoriser
from ..prompt import FRONTIERE_DES_PREUVES
from ..sub_agents.rapport import rapport_par_set_model_response
from ..tools import edit_file, git_lecture, list_files, outil_inconnu, outils_fichiers, outline, run_tests, search
from ..tools._workspace import resolve_in_workspace, workspace
from .fiche import Fiche, lire_fiche, skills_disponibles

_OUTILS = {"search": search, "outline": outline, "list_files": list_files, "git_lecture": git_lecture,
           "edit_file": edit_file, "run_tests": run_tests}


class RapportSousAgent(BaseModel):
    """Rapport commun à tous les sous-agents forgés, validé par ADK (output_schema)."""
    statut: Literal["termine", "partiel", "echec"] = Field(
        description="termine : objectif atteint ; partiel : il reste du travail ; echec : rien de fait")
    fichiers_modifies: list[str] = Field(default_factory=list, description="Fichiers modifiés, relatifs au dépôt")
    resume: str = Field(description="Ce qui a été fait, en 5 lignes maximum")
    incertitudes: list[str] = Field(
        default_factory=list, description="Les points incertains ou non traités, et pourquoi")


def dans_le_perimetre(chemin: str, scope: list[str]) -> bool:
    """Le chemin (relatif au dépôt) correspond-il à un motif du périmètre ?
    « src/billing/** » couvre tout le dossier ; « **/x.py » couvre aussi x.py à la racine."""
    try:
        relatif = resolve_in_workspace(chemin).relative_to(workspace()).as_posix()
    except ValueError:
        return False   # hors du dépôt
    for motif in scope:
        if fnmatch.fnmatchcase(relatif, motif) or (
                motif.startswith("**/") and fnmatch.fnmatchcase(relatif, motif[3:])):
            return True
        if motif.endswith("/**") and relatif == motif[:-3]:
            return True
    return False


def limiter_au_perimetre(scope: list[str]):
    """before_tool_callback : écritures limitées au périmètre de la fiche, puis autorisations."""
    def callback(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
        if tool.name in WRITE_TOOLS:
            chemin = str(args.get("path", ""))
            if not dans_le_perimetre(chemin, scope):
                return {"status": "error",
                        "error": f"{chemin} est hors de ton périmètre ({', '.join(scope)}) : tu ne peux "
                                 "pas le modifier. Signale-le dans tes incertitudes."}
        return autoriser(tool, args, tool_context)
    return callback


def outils(fiche: Fiche) -> list:
    """Les outils de la fiche, ses skills, plus outil_inconnu (réponse aux appels d'outils inexistants)."""
    choisis = [_OUTILS[nom] for nom in fiche.tools if nom in _OUTILS]
    if "write_file" in fiche.tools:
        choisis.append(outils_fichiers(execute=False))           # ReadFile + WriteFile
    elif "read_file" in fiche.tools:
        choisis.append(outils_fichiers(lecture_seule=True))      # ReadFile
    if fiche.skills:
        # Comme pour l'Atelier : le catalogue (nom + description) est dans le prompt (EAGER),
        # les instructions d'une skill n'y entrent qu'au load_skill.
        dossiers = skills_disponibles()
        choisis.append(SkillToolset(skills=[load_skill_from_dir(dossiers[nom]) for nom in fiche.skills],
                                    discovery_mode=SkillDiscoveryMode.EAGER, tool_filter=["load_skill"]))
    return [*choisis, outil_inconnu]


def construire_agent(fiche: Fiche) -> LlmAgent:
    """Le LlmAgent décrit par la fiche, jamais avec plus de droits que l'Atelier."""
    return LlmAgent(
        model=fiche.model,
        name=fiche.name,
        description=fiche.description,
        instruction=fiche.instruction + "\n\nTu ne modifies que ces fichiers : "
                    + ", ".join(fiche.scope) + "\n" + FRONTIERE_DES_PREUVES,
        tools=outils(fiche),
        before_tool_callback=limiter_au_perimetre(fiche.scope),
        output_schema=RapportSousAgent,
        after_tool_callback=tronquer_sorties,
        # Rapport rendu en texte : repassé par set_model_response, où le schéma est validé.
        after_model_callback=rapport_par_set_model_response,
    )


def charger_agent(chemin: Path) -> LlmAgent:
    """Lit, valide et construit le sous-agent d'une fiche .forge/agents/<name>.yaml."""
    return construire_agent(lire_fiche(chemin))
