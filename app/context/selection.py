"""Sélection : à partir de la consigne, choisit les fichiers et les symboles utiles à la tâche.

- symboles mentionnés : un mot de la consigne qui est (ou est contenu dans) un nom
  de fonction ou de classe du dépôt (« filesizeformat » -> do_filesizeformat) ;
- fichiers modifiés pendant la session : ce sur quoi l'agent travaille déjà ;
- voisins dans le graphe d'imports du fichier principal ;
- tests associés : tests/test_<nom du fichier principal>.py.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from .indexer import Index, Symbole

MAX_CORRESPONDANCES = 5   # un mot qui correspond à plus de symboles est trop vague : ignoré
MAX_SYMBOLES = 3
MAX_VOISINS = 4


@dataclass
class Selection:
    principal: str | None = None
    symboles: list[tuple[str, Symbole]] = field(default_factory=list)   # (fichier, symbole)
    voisins: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)


def selectionner(index: Index, consigne: str, fichiers_modifies: list[str]) -> Selection:
    sources = {c: f for c, f in index.fichiers.items() if not est_un_test(c)}
    # Rareté : dans combien de noms de symboles chaque morceau apparaît.
    # « list » ou « environment » sont partout et comptent peu ; « filesizeformat » compte beaucoup.
    frequence = Counter(m for f in sources.values() for s in f.symboles for m in set(morceaux(s.nom)))
    scores = Counter()
    trouves = []

    for mot in mots_de(consigne):
        exacts = [(c, s) for c, f in sources.items() for s in f.symboles if s.nom.lower() == mot]
        partiels = [(c, s) for c, f in sources.items() for s in f.symboles
                    if len(mot) >= 5 and mot in morceaux(s.nom) and s.nom.lower() != mot]
        correspondances = exacts or partiels
        if not correspondances or len(correspondances) > MAX_CORRESPONDANCES:
            continue
        poids = (3 if exacts else 2) / max(frequence[mot], 1)
        for chemin, symbole in correspondances:
            scores[chemin] += poids
            trouves.append((chemin, symbole))
        for chemin in sources:   # nom de fichier cité : « filters », « runtime »...
            if chemin.rsplit("/", 1)[-1].removesuffix(".py") == mot:
                scores[chemin] += 2

    for chemin in fichiers_modifies:
        if chemin in sources:
            scores[chemin] += 4

    if not scores:
        return Selection()
    principal = scores.most_common(1)[0][0]

    # Symboles à montrer en entier : d'abord ceux du fichier principal, puis les plus rares.
    symboles = sorted(dict.fromkeys(trouves),
                      key=lambda t: (t[0] != principal, frequence[t[1].nom.lower()]))[:MAX_SYMBOLES]
    voisins = [c for c, _ in scores.most_common() if c != principal]
    voisins += sorted(sources[principal].imports) + index.importe_par(principal)
    voisins = [c for c in dict.fromkeys(voisins) if c != principal and not est_un_test(c)][:MAX_VOISINS]

    nom = principal.rsplit("/", 1)[-1]
    tests = [c for c in index.fichiers if est_un_test(c) and c.rsplit("/", 1)[-1] == f"test_{nom}"]
    return Selection(principal, symboles, voisins, tests)


def mots_de(texte: str) -> list[str]:
    """Identifiants candidats de la consigne, en minuscules, sans doublon.
    On découpe d'abord en mots entiers (accents compris), puis on ne garde que
    ceux qui ressemblent à un identifiant : « éléments » ne devient pas « ments »."""
    mots = [m for m in re.findall(r"\w+", texte) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{3,}", m)]
    return list(dict.fromkeys(m.lower() for m in mots))


def morceaux(nom: str) -> list[str]:
    """Morceaux d'un nom : do_filesizeformat -> [do, filesizeformat] ;
    visit_EvalContextModifier -> [visit, eval, context, modifier]."""
    return [m.lower() for m in re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", nom)]


def est_un_test(chemin: str) -> bool:
    nom = chemin.rsplit("/", 1)[-1]
    return chemin.startswith("tests/") or "/tests/" in chemin or nom.startswith("test_") or nom == "conftest.py"
