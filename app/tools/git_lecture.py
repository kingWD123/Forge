"""Outil git_lecture : l'historique et la recherche de git, en lecture seule.

Utile dans les grands dépôts : git grep est rapide, git log et git blame disent
ce qui a changé récemment et pourquoi. Seules quelques sous-commandes sont permises,
lancées sans shell (donc sans enchaînement ni redirection possibles).
"""

import shlex
import subprocess

from ._workspace import workspace

SOUS_COMMANDES = {"log", "show", "blame", "diff", "grep", "ls-files", "status"}
# Options qui écriraient un fichier ou lanceraient un programme.
OPTIONS_INTERDITES = ("--output", "-O", "--open-files-in-pager", "--ext-diff", "--textconv")
MAX_CARACTERES = 8_000


def git_lecture(commande: str) -> dict:
    """Lance une commande git en lecture seule dans le dépôt.

    Sous-commandes permises : log, show, blame, diff, grep, ls-files, status.

    Args:
      commande: ex. "log --oneline -15 -- src/jinja2/filters.py",
        "blame -L 700,730 src/jinja2/filters.py", "grep -n do_round".

    Returns:
      sortie : la sortie de git (début et fin si elle est trop longue) ; code : code de retour.
    """
    arguments = shlex.split(commande, posix=True)
    if arguments[:1] == ["git"]:
        arguments = arguments[1:]
    if not arguments or arguments[0] not in SOUS_COMMANDES:
        raise ValueError(f"Sous-commande non permise. Permises : {', '.join(sorted(SOUS_COMMANDES))}.")
    if any(a.startswith(OPTIONS_INTERDITES) for a in arguments[1:]):
        raise ValueError("Option interdite : elle pourrait écrire un fichier ou lancer un programme.")

    proc = subprocess.run(["git", "--no-pager", *arguments], cwd=workspace(), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)
    sortie = (proc.stdout + proc.stderr).strip()
    if len(sortie) > MAX_CARACTERES:   # début et fin, comme pour Execute
        moitie = MAX_CARACTERES // 2
        sortie = f"{sortie[:moitie]}\n… [sortie trop longue, milieu retiré] …\n{sortie[-moitie:]}"
    return {"sortie": sortie, "code": proc.returncode}
