"""Outil references : où un symbole est défini, où il est utilisé, et qui importe son fichier.

Réutilise l'index du Compilateur (indexer.py) et l'outil search.
"""

import re

from ..tools import search, workspace
from .indexer import indexer


def references(symbole: str) -> dict:
    """Trouve où un symbole (fonction, classe, méthode) est défini et où il est utilisé.

    Utile pour mesurer l'impact d'un changement ou faire l'inventaire des usages.

    Args:
      symbole: nom exact du symbole, ex. "do_round" ou "LoopContext".

    Returns:
      definitions : "chemin:début-fin  signature" pour chaque définition ;
      utilisations : lignes qui citent le symbole (hors définitions), avec la fonction englobante ;
      importe_par : fichiers du dépôt qui importent un fichier où le symbole est défini.
    """
    index = indexer(workspace())
    definitions = [(chemin, s) for chemin, f in index.fichiers.items() for s in f.symboles if s.nom == symbole]

    resultat = search(rf"\b{re.escape(symbole)}\b", max_results=30)
    lignes_de_definition = {f"{chemin}:{s.debut}" for chemin, s in definitions}
    utilisations = [m for m in resultat["matches"]
                    if m.split(" ", 1)[0].rstrip(":") not in lignes_de_definition]

    importe_par = sorted({i for chemin, _ in definitions for i in index.importe_par(chemin)})
    return {
        "definitions": [f"{chemin}:{s.debut}-{s.fin}  {s.signature}" for chemin, s in definitions],
        "utilisations": utilisations,
        "utilisations_tronquees": resultat["truncated"],
        "importe_par": importe_par,
    }
