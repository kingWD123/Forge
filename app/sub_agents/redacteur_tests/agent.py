"""Rédacteur de tests : écrit des tests, uniquement dans les fichiers de tests."""

import os
from pathlib import PurePosixPath
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ...context.troncature import tronquer_sorties
from ...permissions import WRITE_TOOLS, autoriser
from ...tools import edit_file, outils_fichiers, outline, run_tests, search
from ...tools._workspace import resolve_in_workspace, workspace
from . import prompt
from .schema import RapportTests


def est_fichier_de_test(chemin: str) -> bool:
    """Dossier tests/ (ou test/), ou fichier test_*.py, *_test.py, conftest.py."""
    try:
        relatif = PurePosixPath(resolve_in_workspace(chemin).relative_to(workspace()).as_posix())
    except ValueError:
        return False   # hors du dépôt
    nom = relatif.name
    return (any(partie in ("tests", "test") for partie in relatif.parts[:-1])
            or (nom.startswith("test_") and nom.endswith(".py"))
            or nom.endswith("_test.py") or nom == "conftest.py")


def limiter_aux_tests(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """Le rédacteur ne peut écrire que dans des fichiers de tests ; les autorisations
    habituelles s'appliquent ensuite."""
    if tool.name in WRITE_TOOLS and not est_fichier_de_test(str(args.get("path", ""))):
        return {"status": "error",
                "error": f"Tu ne peux écrire que dans des fichiers de tests (tests/, test_*.py), "
                         f"pas dans {args.get('path')}. Si le code source est faux, signale-le dans bugs."}
    return autoriser(tool, args, tool_context)


redacteur_tests = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="redacteur_tests",
    description=(
        "Écrit des tests pytest précis pour un module, une fonction ou un comportement, uniquement "
        "dans tests/, et signale les bugs qu'ils révèlent. Donne-lui le module ou le comportement "
        "à couvrir et ce qu'on attend."
    ),
    instruction=prompt.REDACTEUR_TESTS_PROMPT,
    # Pas d'Execute : il lance les tests avec run_tests, et n'a pas besoin du shell.
    tools=[search, outline, edit_file, run_tests, outils_fichiers(execute=False)],
    before_tool_callback=limiter_aux_tests,
    output_schema=RapportTests,
    after_tool_callback=tronquer_sorties,
)
