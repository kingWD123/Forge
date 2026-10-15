"""Assemblage du bloc de contexte compilé : compression et ordonnancement.

Le bloc est placé en tête de la requête (instruction système), dans cet ordre de priorité :
  0. état de la tâche : objectif, contraintes épinglées, fichiers modifiés, décisions (etat.py)
     (en tête : le modèle lit mieux le début)
  1. instructions du projet (AGENTS.md, s'il existe)
  2. code des symboles visés, en entier (le fichier principal d'abord)
  3. tests associés
  4. carte du fichier principal        (signatures seulement : compression)
  5. fichiers liés par les imports     (signatures seulement : la périphérie)
Si le budget est dépassé, les dernières sections sont coupées.
Le code est relu sur le disque à chaque appel : les numéros de ligne sont toujours à jour.
"""

from pathlib import Path

from .etat import afficher
from .indexer import indexer
from .selection import selectionner

BUDGET = 12_000                 # caractères, environ 3 000 tokens
MAX_LIGNES_SYMBOLE = 60
MAX_SIGNATURES_VOISIN = 15
MAX_INSTRUCTIONS_PROJET = 3_000


def contexte_compile(racine: Path, etat: dict) -> str:
    index = indexer(racine)
    # On cherche les symboles dans l'objectif ET dans le dernier message (qui peut préciser).
    texte = f"{etat['objectif']}\n{etat['dernier_message']}"
    selection = selectionner(index, texte, etat["fichiers_touches"])
    section_etat = afficher(etat)
    instructions = instructions_du_projet(racine)
    if not selection.principal and not section_etat and not instructions:
        return ""

    sections = []
    if section_etat:
        sections.append(section_etat)
    if instructions:
        sections.append("## Instructions du projet (AGENTS.md)\n" + instructions)
    if selection.symboles:
        extraits = [extrait(racine, chemin, symbole) for chemin, symbole in selection.symboles]
        sections.append("## Code à examiner en priorité\n" + "\n\n".join(extraits))
    if selection.tests:
        sections.append("## Tests associés\n" + "\n".join(f"- {t}  (run_tests(\"{t}\"))" for t in selection.tests))
    if selection.principal:
        carte = [f"l.{s.debut}-{s.fin}  {s.signature}" for s in index.fichiers[selection.principal].symboles]
        sections.append(f"## Carte de {selection.principal}\n" + "\n".join(carte))
    for voisin in selection.voisins:
        signatures = [f"l.{s.debut}  {s.signature}" for s in index.fichiers[voisin].symboles]
        suite = len(signatures) - MAX_SIGNATURES_VOISIN
        sections.append(f"## Fichier lié : {voisin}\n" + "\n".join(signatures[:MAX_SIGNATURES_VOISIN])
                        + (f"\n… ({suite} autres : outline(\"{voisin}\"))" if suite > 0 else ""))

    entete = ("# Contexte compilé par FORGE CODE\n"
              "Extraits du dépôt choisis pour cette tâche et relus avant chaque appel : "
              "les numéros de ligne sont à jour. Ce contexte est pour toi : sers-t'en, "
              "mais ne le recopie pas dans tes réponses.")
    return respecter_budget([entete, *sections])


def instructions_du_projet(racine: Path) -> str:
    """Le fichier AGENTS.md à la racine du dépôt (conventions, commandes de test...), s'il existe."""
    fichier = racine / "AGENTS.md"
    if not fichier.is_file():
        return ""
    texte = fichier.read_text(encoding="utf-8").strip()
    if len(texte) > MAX_INSTRUCTIONS_PROJET:
        texte = texte[:MAX_INSTRUCTIONS_PROJET] + "\n… (suite : ReadFile AGENTS.md)"
    return texte


def extrait(racine: Path, chemin: str, symbole) -> str:
    """Le code d'un symbole, avec ses numéros de ligne (coupé au-delà de MAX_LIGNES_SYMBOLE)."""
    lignes = (racine / chemin).read_text(encoding="utf-8").splitlines()
    fin = min(symbole.fin, symbole.debut + MAX_LIGNES_SYMBOLE - 1)
    code = "\n".join(f"{n:>5}  {lignes[n - 1]}" for n in range(symbole.debut, fin + 1) if n <= len(lignes))
    suite = (f"\n… (suite : ReadFile {chemin} l.{fin + 1}-{symbole.fin})" if fin < symbole.fin else "")
    return f"### {chemin} — {symbole.nom} (l.{symbole.debut}-{symbole.fin})\n{code}{suite}"


def respecter_budget(sections: list[str]) -> str:
    """Ajoute les sections dans l'ordre tant qu'elles tiennent ; coupe la première qui déborde."""
    texte = ""
    for section in sections:
        separateur = "\n\n" if texte else ""
        reste = BUDGET - len(texte) - len(separateur)
        if reste <= 200:
            break
        bloc = section if len(section) <= reste else section[:reste] + "\n… (coupé : budget atteint)"
        texte += separateur + bloc
    return texte
