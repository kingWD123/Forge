"""Outil experimenter : exécute un court script Python dans le dépôt, sans écrire de fichier.

Pour diagnostiquer, lire le code ne suffit pas toujours : on réduit le problème à un cas
minimal, puis on observe les valeurs intermédiaires (jetons, arbre, code généré, retour de
chaque fonction) pour trouver la première étape où la valeur devient fausse.

Lecture seule : le script ne peut ni écrire, ni supprimer, ni déplacer un fichier (open en
écriture, os.remove, shutil.rmtree... lèvent PermissionError). Les .pyc que Python écrit
lui-même restent possibles.
"""

import os
import subprocess

from ..context.troncature import couper_debut_et_fin
from ._workspace import workspace
from .run_tests import _python_for

_LIMITE_SORTIE = 6_000
_DELAI_S = 60

# Exécuté avant le script : remplace les fonctions qui écrivent par un refus.
_LECTURE_SEULE = '''
import builtins as _b, io as _io, os as _os, shutil as _sh
def _refus(*_a, **_k):
    raise PermissionError("experimenter est en lecture seule : n'écris, ne supprime et ne déplace aucun fichier")
_ouvrir = _b.open
def _ouvrir_en_lecture(fichier, mode="r", *a, **k):
    if any(c in mode for c in "wax+"):
        _refus()
    return _ouvrir(fichier, mode, *a, **k)
_b.open = _io.open = _ouvrir_en_lecture
for _nom in ("remove", "unlink", "rename", "replace", "rmdir", "removedirs", "mkdir", "makedirs",
             "truncate", "system"):
    setattr(_os, _nom, _refus)
for _nom in ("rmtree", "move", "copy", "copy2", "copyfile", "copytree"):
    setattr(_sh, _nom, _refus)
del _nom
'''


def experimenter(code: str) -> dict:
    """Exécute un court script Python dans le dépôt, en lecture seule, et renvoie sa sortie.
    Sert à reproduire un échec sur un cas minimal et à afficher les valeurs intermédiaires
    (avec print) pour trouver où une valeur devient fausse.

    Args:
      code: le script Python (ex. "from jinja2 import Environment\\n
        print(Environment().from_string('{{ 1 }} - {{ 2 }}').render())"). Il importe le code
        du dépôt ; il ne peut écrire aucun fichier. 60 secondes au plus.

    Returns:
      status : ok, error (le script a levé une exception) ou timeout ;
      sortie : ce que le script a affiché (stdout puis stderr, coupé s'il est très long).
    """
    racine = workspace()
    try:
        proc = subprocess.run([_python_for(racine), "-c", _LECTURE_SEULE + "\n" + code], cwd=racine,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=_DELAI_S, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "sortie": f"Le script a dépassé {_DELAI_S} s : simplifie-le."}
    sortie = proc.stdout + (("\n" + proc.stderr) if proc.stderr.strip() else "")
    return {"status": "ok" if proc.returncode == 0 else "error",
            "sortie": couper_debut_et_fin(sortie.strip(), _LIMITE_SORTIE)}
