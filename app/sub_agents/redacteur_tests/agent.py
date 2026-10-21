"""Rédacteur de tests : écrit des tests, uniquement dans les fichiers de tests."""

import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ...context.troncature import tronquer_sorties
from ...permissions import WRITE_TOOLS, autoriser
from ...tools import edit_file, outil_inconnu, outils_fichiers, outline, run_tests, search
from ...tools._workspace import est_fichier_de_test
from . import prompt
from .schema import RapportTests


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
        "QUAND : dès que la consigne demande d'écrire, d'ajouter ou de compléter des tests ; ne les "
        "écris pas toi-même. QUOI : écrit des tests pytest précis, uniquement dans tests/, et "
        "signale les bugs qu'ils révèlent. DONNE-LUI : le module ou le comportement à couvrir, ce "
        "qui est attendu et les contraintes de la consigne."
    ),
    instruction=prompt.REDACTEUR_TESTS_PROMPT,
    # Pas d'Execute : il lance les tests avec run_tests, et n'a pas besoin du shell.
    tools=[search, outline, edit_file, run_tests, outils_fichiers(execute=False), outil_inconnu],
    before_tool_callback=limiter_aux_tests,
    output_schema=RapportTests,
    after_tool_callback=tronquer_sorties,
)
