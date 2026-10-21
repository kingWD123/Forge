"""Plugin VerificationApresEcriture : juste après une modification réussie d'un module Python,
on essaie de l'importer, et on signale tout de suite s'il ne s'importe plus.

Le contrôle de syntaxe d'edit_file n'attrape pas un nom indéfini ou un import cassé : sans
ce plugin, l'agent ne le découvrait qu'au run_tests suivant, après avoir construit dessus


Pas de fausse alerte : on importe le module juste AVANT et juste APRÈS la modification, et
on ne signale que si l'erreur est nouvelle et se produit dans le fichier modifié. Un dépôt
déjà cassé (par exemple au début d'une migration) ne déclenche donc rien.
Seuls les modules d'un paquet sont importés (pas les tests, ni les scripts isolés),
avec un délai maximal. Plugin : les spécialistes qui écrivent en héritent.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from app.context.indexer import nom_de_module
from app.tools._workspace import est_fichier_de_test, resolve_in_workspace, workspace
from app.tools.run_tests import _python_for

DELAI_SECONDES = 30


ECRITURES = ("edit_file", "WriteFile")


class VerificationApresEcriture(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="verification_apres_ecriture")
        self._erreurs_avant: dict[str, str] = {}   # fichier -> erreur d'import avant la modification

    async def before_tool_callback(self, *, tool: BaseTool, tool_args: dict[str, Any],
                                   tool_context: ToolContext) -> Optional[dict]:
        if tool.name in ECRITURES:
            chemin = str(tool_args.get("path", ""))
            self._erreurs_avant[chemin] = erreur_import(chemin)
        return None

    async def after_tool_callback(self, *, tool: BaseTool, tool_args: dict[str, Any],
                                  tool_context: ToolContext, result: Any) -> Optional[dict]:
        if tool.name not in ECRITURES or not isinstance(result, dict):
            return None
        chemin = str(tool_args.get("path", ""))
        avant = self._erreurs_avant.pop(chemin, "")
        if result.get("error") or result.get("status") == "error":
            return None   # rien n'a été écrit
        probleme = verifier_import(chemin, erreur_avant=avant)
        return {**result, "verification": probleme} if probleme else None


def verifier_import(chemin: str, erreur_avant: str = "") -> str:
    """'' si rien à signaler, sinon le message d'alerte : l'import échoue après la modification,
    l'erreur est nouvelle (différente de celle d'avant) et elle se produit dans ce fichier."""
    erreur = erreur_import(chemin, seulement_dans_le_fichier=True)
    if not erreur or erreur == erreur_avant:
        return ""
    return (f"⚠ {chemin} ne s'importe plus après cette modification : {erreur}. "
            "Corrige-le avant de continuer (sauf si ta modification de ce fichier n'est pas finie).")


def erreur_import(chemin: str, seulement_dans_le_fichier: bool = False) -> str:
    """La dernière ligne de l'erreur d'import du module, ou '' s'il s'importe (ou n'est pas
    vérifiable). Avec seulement_dans_le_fichier : '' si l'erreur vient d'un autre fichier."""
    try:
        fichier = resolve_in_workspace(chemin)
    except ValueError:
        return ""
    if fichier.suffix != ".py" or est_fichier_de_test(chemin) or not (fichier.parent / "__init__.py").is_file():
        return ""   # pas un module de paquet : rien à importer sans risque
    racine = workspace()
    module = nom_de_module(fichier.relative_to(racine).as_posix())
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        [str(racine / "src"), str(racine), os.environ.get("PYTHONPATH", "")])}
    try:
        proc = subprocess.run([_python_for(racine), "-c", f"import {module}"], cwd=racine, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=DELAI_SECONDES)
    except subprocess.TimeoutExpired:
        return ""
    if proc.returncode == 0 or not proc.stderr.strip():
        return ""
    if seulement_dans_le_fichier and not erreur_dans(proc.stderr, fichier):
        return ""
    return proc.stderr.strip().splitlines()[-1]


def erreur_dans(trace: str, fichier: Path) -> bool:
    """La dernière ligne de code exécutée dans la trace est-elle dans ce fichier ?"""
    lieux = re.findall(r'File "([^"]+)", line \d+', trace)
    return bool(lieux) and Path(lieux[-1]).resolve() == fichier.resolve()
