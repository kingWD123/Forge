"""Autorisations de l'Atelier : before_tool_callback qui laisse passer, demande ou bloque.

Trois décisions :
- allow : l'outil s'exécute sans rien demander (lectures, recherche, tests, liste blanche) ;
- ask   : l'Atelier se met en pause et demande l'accord de l'utilisateur (confirmation ADK) ;
- deny  : l'appel est refusé, quel que soit le mode.

Trois modes (FORGE_PERMISSION_MODE) :
- ask (défaut) : écritures et commandes hors liste blanche demandent l'accord ;
- auto-edit    : écritures autorisées, commandes hors liste blanche demandent l'accord ;
- auto         : tout est autorisé, sauf ce qui est bloqué.
"""

import os
import re
from typing import Any, Literal

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from .tools._workspace import resolve_in_workspace
from .tools.edit_file import make_diff, prepare_edit

Decision = Literal["allow", "ask", "deny"]

# Outils sans effet de bord sur le dépôt.
READ_TOOLS = {"ReadFile", "search", "outline", "run_tests", "noter_decision"}
# Sous-agents appelés comme outils : ils n'agissent qu'à travers leurs propres outils.
AGENT_TOOLS = {"evaluateur_agent", "forgeron_agent", "banc_essai_agent", "verificateur_agent",
               "explorateur", "diagnostiqueur", "migrateur", "redacteur_tests",
               # Lance des migrateurs : leurs écritures passent par ces mêmes autorisations.
               "migrer_partout"}
WRITE_TOOLS = {"edit_file", "WriteFile"}
EXEC_TOOL = "Execute"

# Commandes autorisées sans demander, si elles sont seules (pas de chaînage ni redirection).
ALLOWED_COMMAND_PREFIXES = (
    "git status", "git diff", "git log", "git show", "git branch",
    "pytest", "python -m pytest",
    "dir", "ls",
)

# Toujours refusées, quel que soit le mode.
DENIED_COMMAND_PATTERNS = (
    (r"\bgit\s+push\b", "pousser vers un dépôt distant est interdit sans accord explicite hors de l'agent"),
    (r"(^|[\s\\/\"'=])\.env(?!\.example)\b", "les fichiers .env contiennent des secrets"),
    (r"\b(shutdown|format|mkfs|diskpart)\b", "commande système dangereuse"),
    (r"\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\*)", "suppression récursive dangereuse"),
)

_CHAINING = re.compile(r"&&|\|\||[;|<>`]|\$\(")


def permission_mode() -> str:
    mode = os.getenv("FORGE_PERMISSION_MODE", "ask").strip().lower()
    return mode if mode in ("ask", "auto-edit", "auto") else "ask"


def _fichier_existe(chemin: str) -> bool:
    try:
        return resolve_in_workspace(chemin).is_file()
    except ValueError:
        return False   # chemin hors du dépôt : l'outil le refusera lui-même


def decide(tool_name: str, args: dict[str, Any], mode: str | None = None) -> tuple[Decision, str]:
    """Décide pour un appel d'outil. Renvoie (décision, raison)."""
    mode = mode or permission_mode()

    if tool_name in READ_TOOLS or tool_name in AGENT_TOOLS:
        return "allow", "lecture seule"

    if tool_name == "WriteFile" and _fichier_existe(args.get("path", "")):
        # Réécrire un fichier entier fait perdre du code : on modifie avec edit_file.
        return "deny", "WriteFile ne sert qu'à créer un nouveau fichier ; pour modifier un fichier existant, utilise edit_file"

    if tool_name in WRITE_TOOLS:
        if mode in ("auto-edit", "auto"):
            return "allow", f"écriture autorisée en mode {mode}"
        return "ask", "écriture dans le dépôt"

    if tool_name == EXEC_TOOL:
        command = str(args.get("command", "")).strip()
        for pattern, reason in DENIED_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return "deny", reason
        if _is_allowed_command(command):
            return "allow", "commande en liste blanche"
        if mode == "auto":
            return "allow", "commande autorisée en mode auto"
        return "ask", "commande hors liste blanche"

    # Outil inconnu (ajouté plus tard sans règle) : on demande.
    if mode == "auto":
        return "allow", "outil autorisé en mode auto"
    return "ask", "outil sans règle d'autorisation"


def _is_allowed_command(command: str) -> bool:
    if not command or _CHAINING.search(command):
        return False
    lowered = command.lower()
    return any(lowered == p or lowered.startswith(p + " ") for p in ALLOWED_COMMAND_PREFIXES)


def describe(tool_name: str, args: dict[str, Any]) -> str:
    """Texte montré à l'utilisateur quand on lui demande son accord."""
    if tool_name == EXEC_TOOL:
        return f"Exécuter la commande : {args.get('command', '')}"
    if tool_name == "edit_file":
        diff = make_diff(args.get("path", "?"), args.get("old_string", ""), args.get("new_string", ""))
        return f"Modifier {args.get('path', '?')} :\n{diff}"
    if tool_name == "WriteFile":
        content = str(args.get("content", ""))
        return f"Créer {args.get('path', '?')} ({len(content.splitlines())} lignes)"
    return f"Appeler {tool_name}({_shorten(str(args))})"


def _shorten(text: str, limit: int = 300) -> str:
    text = str(text).replace("\n", "\n    ")
    return text if len(text) <= limit else text[:limit] + "…"


def _edit_is_possible(args: dict[str, Any]) -> bool:
    try:
        prepare_edit(args.get("path", ""), args.get("old_string", ""), args.get("new_string", ""))
        return True
    except ValueError:
        return False


def autoriser(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> dict | None:
    """before_tool_callback : None laisse l'outil s'exécuter, un dict remplace sa réponse."""
    decision, reason = decide(tool.name, args)

    if decision == "deny":
        return {"status": "error", "error": f"Refusé par les règles de sécurité : {reason}."}
    if decision == "allow":
        return None

    if tool.name == "edit_file" and not _edit_is_possible(args):
        # Rien ne sera écrit : inutile de demander, l'outil renverra l'erreur au modèle.
        return None

    confirmation = tool_context.tool_confirmation
    if confirmation is None:
        # Pause : ADK envoie une demande de confirmation à l'utilisateur,
        # puis relance cet appel avec sa réponse dans tool_context.tool_confirmation.
        tool_context.request_confirmation(hint=f"{describe(tool.name, args)}\n({reason})")
        tool_context.actions.skip_summarization = True
        return {"status": "pending", "error": "En attente de l'accord de l'utilisateur."}
    if not confirmation.confirmed:
        return {
            "status": "error",
            "error": "L'utilisateur a refusé cette action. Ne la retente pas telle quelle : "
                     "demande-lui comment procéder.",
        }
    return None
