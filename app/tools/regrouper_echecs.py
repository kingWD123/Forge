"""Outil regrouper_echecs : regroupe les tests en échec par type d'erreur.

Face à 96 échecs, l'important n'est pas chaque test mais ce qu'ils ont en commun :
« 90 échecs avec la même AssertionError » pointe vers une cause unique dans le code.
"""

import os
import re
import subprocess
from collections import defaultdict

from ._workspace import resolve_in_workspace, workspace
from .run_tests import _python_for

MAX_GROUPES = 8


def regrouper_echecs(target: str = "") -> dict:
    """Lance les tests et regroupe TOUS les échecs par message d'erreur, du groupe le plus
    gros au plus petit. Utile quand beaucoup de tests échouent : un gros groupe pointe
    vers une cause commune.

    Args:
      target: fichier ou dossier de tests, relatif au dépôt. Vide = tous les tests.

    Returns:
      total_echecs ; groupes : pour chacun, nombre, erreur (message normalisé),
      exemple (un message réel), tests (3 exemples) et fichiers_de_tests concernés.
    """
    racine = workspace()
    commande = [_python_for(racine), "-m", "pytest", "-q", "--tb=no", "-rfE",
                "--no-header", "-p", "no:cacheprovider", "--color=no"]
    if target:
        resolve_in_workspace(target.split("::", 1)[0])   # refuse un chemin hors du dépôt
        commande.append(target)
    # Une ligne large pour que pytest ne coupe pas les messages d'erreur.
    proc = subprocess.run(commande, cwd=racine, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300, env={**os.environ, "COLUMNS": "300"})

    groupes = defaultdict(list)   # message normalisé -> [(test, message réel)]
    for ligne in proc.stdout.splitlines():
        m = re.match(r"^(?:FAILED|ERROR) (\S+)(?: - (.*))?$", ligne)
        if m:
            message = m.group(2) or "(pas de message)"
            groupes[normaliser(message)].append((m.group(1), message))

    tries = sorted(groupes.items(), key=lambda g: len(g[1]), reverse=True)
    return {
        "total_echecs": sum(len(tests) for tests in groupes.values()),
        "groupes": [{
            "nombre": len(tests),
            "erreur": erreur,
            "exemple": tests[0][1][:200],
            "tests": [t for t, _ in tests[:3]],
            "fichiers_de_tests": sorted({t.split("::")[0] for t, _ in tests}),
        } for erreur, tests in tries[:MAX_GROUPES]],
        "autres_groupes": max(len(tries) - MAX_GROUPES, 0),
    }


def normaliser(message: str) -> str:
    """Rend comparables des messages de même nature : textes entre guillemets -> '…',
    nombres -> N.  « assert 'a b' == 'ab' » et « assert 'x y' == 'xy' » se regroupent."""
    message = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", message)
    message = re.sub(r"\d+", "N", message)
    return re.sub(r"\s+", " ", message).strip()[:120]
