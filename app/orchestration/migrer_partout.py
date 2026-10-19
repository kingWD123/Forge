"""Outil migrer_partout : la migration d'un code dans tout le dépôt, en un seul appel.

L'Atelier n'a qu'une décision à prendre (« c'est une migration ») ; le reste est du code :
1. inventaire des fichiers qui contiennent l'ancien code (search) ;
2. un migrateur par fichier, en parallèle ;
3. search final : reste-t-il l'ancien code ?
"""

import asyncio
import fnmatch
import re

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from ..sub_agents.migrateur import migrateur
from ..tools import search

# Migrateurs lancés en même temps (limite les appels simultanés au modèle).
MIGRATEURS_EN_PARALLELE = 4
_MAX_RESULTATS = 10_000


def motif(ancien: str) -> str:
    """Expression régulière de l'ancien code, en mot entier quand il commence et finit
    par une lettre : « internalcode » ne doit pas trouver « is_internalcode_x »."""
    m = re.escape(ancien)
    if re.match(r"\w", ancien):
        m = r"\b" + m
    if re.search(r"\w$", ancien):
        m = m + r"\b"
    return m


def _exclu(chemin: str, exclure: list[str]) -> bool:
    for e in exclure:
        e = e.replace("\\", "/").removeprefix("./").rstrip("/")
        if chemin == e or chemin.startswith(e + "/") or fnmatch.fnmatch(chemin, e):
            return True
    return False


def inventaire(ancien: str, path: str = ".", glob: str = "", exclure: list[str] | None = None) -> dict[str, list[str]]:
    """Occurrences de l'ancien code, regroupées par fichier (fichiers exclus retirés)."""
    lignes = search(motif(ancien), path=path, glob=glob, max_results=_MAX_RESULTATS)["matches"]
    par_fichier: dict[str, list[str]] = {}
    for ligne in lignes:
        chemin = ligne.split(":", 1)[0]
        if not _exclu(chemin, exclure or []):
            par_fichier.setdefault(chemin, []).append(ligne)
    return par_fichier


def demande_au_migrateur(fichier: str, ancien: str, nouveau: str, regle: str, exemple: str,
                         occurrences: list[str]) -> str:
    texte = (f"Fichier confié : {fichier}\n"
             f"Règle : {regle}\n"
             f"Ancien code : {ancien}\n"
             f"Nouveau code : {nouveau}\n")
    if exemple:
        texte += f"Exemple : {exemple}\n"
    texte += "Occurrences repérées dans ce fichier (les numéros de ligne changent après chaque modification) :\n"
    return texte + "\n".join(f"- {o}" for o in occurrences)


async def lancer_migrateur(demande: str, tool_context: ToolContext) -> dict:
    """Lance le migrateur sur une demande, comme le ferait l'Atelier (AgentTool)."""
    rapport = await AgentTool(agent=migrateur).run_async(args={"request": demande}, tool_context=tool_context)
    if not isinstance(rapport, dict):
        # Pas de rapport structuré : erreur du modèle, limite d'appels...
        return {"statut": "erreur", "erreur": str(rapport)[:500]}
    return rapport


async def migrer_partout(
    ancien: str,
    nouveau: str,
    regle: str,
    tool_context: ToolContext,
    exemple: str = "",
    path: str = ".",
    glob: str = "",
    exclure: list[str] | None = None,
) -> dict:
    """Migre un code dans TOUT le dépôt : renommage, API remplacée, import déplacé...
    Trouve les fichiers qui contiennent l'ancien code, confie chacun à un migrateur
    (en parallèle), puis vérifie qu'il ne reste plus l'ancien code.

    Args:
      ancien: l'ancien code tel qu'il apparaît dans les fichiers (ex. "internalcode").
      nouveau: ce qui le remplace (ex. "mark_internal").
      regle: la règle à appliquer, en une ou deux phrases (ex. "le décorateur internalcode
        s'appelle maintenant mark_internal ; remplace aussi le nom dans les chaînes et
        les commentaires").
      exemple: facultatif, un exemple avant/après.
      path: dossier où chercher, relatif au dépôt. Par défaut tout le dépôt.
      glob: filtre sur les noms de fichiers (ex. "*.py"). Vide = tous.
      exclure: fichiers ou dossiers à ne pas modifier (ex. ["tests", "src/pkg/utils.py"]) :
        ceux que la consigne interdit de toucher, et les tests.

    Returns:
      statut : migre (plus aucune occurrence), partiel (il en reste) ou rien_a_faire ;
      fichiers : pour chaque fichier, le statut du migrateur, le nombre de modifications
        et ses incertitudes ;
      occurrences_restantes : les lignes qui contiennent encore l'ancien code ;
      ensuite : ce qu'il te reste à faire.
    """
    exclure = exclure or []
    a_migrer = inventaire(ancien, path, glob, exclure)
    if not a_migrer:
        return {"statut": "rien_a_faire", "fichiers": {}, "occurrences_restantes": [],
                "ensuite": f"Aucun fichier non exclu ne contient « {ancien} »."}

    limite = asyncio.Semaphore(MIGRATEURS_EN_PARALLELE)

    async def migrer(fichier: str) -> dict:
        async with limite:
            demande = demande_au_migrateur(fichier, ancien, nouveau, regle, exemple, a_migrer[fichier])
            try:
                return await lancer_migrateur(demande, tool_context)
            except Exception as e:  # un fichier en échec n'arrête pas les autres
                return {"statut": "erreur", "erreur": f"{type(e).__name__}: {e}"[:500]}

    rapports = await asyncio.gather(*(migrer(f) for f in a_migrer))

    fichiers = {}
    for fichier, rapport in zip(a_migrer, rapports):
        resume = {"statut": rapport.get("statut"), "modifications": len(rapport.get("modifications", []))}
        for cle in ("incertitudes", "erreur"):
            if rapport.get(cle):
                resume[cle] = rapport[cle]
        fichiers[fichier] = resume

    # Vérification sur toute la zone, pas seulement sur les fichiers migrés.
    restantes = [o for occ in inventaire(ancien, path, glob, exclure).values() for o in occ]
    return {
        "statut": "partiel" if restantes else "migre",
        "fichiers": fichiers,
        "occurrences_restantes": restantes[:50],
        "ensuite": ("Corrige toi-même les occurrences restantes avec edit_file, puis lance les tests."
                    if restantes else "Lance maintenant les tests."),
    }
