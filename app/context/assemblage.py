"""Assemblage du bloc de contexte compilé : compression et ordonnancement.

Le bloc est placé en tête de la requête (instruction système), dans cet ordre de priorité :
  0. instructions du projet (AGENTS.md, s'il existe : le standard de Codex et d'autres agents)
  1. contraintes de la consigne        (en tête : le modèle lit mieux le début)
  2. code des symboles visés, en entier (le fichier principal d'abord)
  3. tests associés
  4. carte du fichier principal        (signatures seulement : compression)
  5. fichiers liés par les imports     (signatures seulement : la périphérie)
Si le budget est dépassé, les dernières sections sont coupées.
Le code est relu sur le disque à chaque appel : les numéros de ligne sont toujours à jour.
"""

import re
from pathlib import Path

from .indexer import indexer
from .selection import selectionner

BUDGET = 12_000                 # caractères, environ 3 000 tokens
MAX_LIGNES_SYMBOLE = 60
MAX_SIGNATURES_VOISIN = 15
MAX_INSTRUCTIONS_PROJET = 3_000

_MOTS_DE_CONTRAINTE = re.compile(
    r"\bne\b|\bn['’]|\bsans\b|\bjamais\b|\binterdit|\bcontrainte|\buniquement\b|\bseulement\b"
    r"|\bdoit\b|\bdoivent\b", re.IGNORECASE)


def extraire_contraintes(consigne: str) -> list[str]:
    """Les phrases de la consigne qui posent une règle (« ne modifie que... », « sans... »)."""
    phrases = re.split(r"(?<=[.!?])\s+|\n", consigne)
    return [p.strip() for p in phrases if p.strip() and _MOTS_DE_CONTRAINTE.search(p)]


def contexte_compile(racine: Path, consigne: str, fichiers_modifies: list[str]) -> str:
    index = indexer(racine)
    selection = selectionner(index, consigne, fichiers_modifies)
    contraintes = extraire_contraintes(consigne)
    instructions = instructions_du_projet(racine)
    if not selection.principal and not contraintes and not instructions:
        return ""

    sections = []
    if instructions:
        sections.append("## Instructions du projet (AGENTS.md)\n" + instructions)
    if contraintes:
        sections.append("## Contraintes à respecter\n" + "\n".join(f"- {c}" for c in contraintes))
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
              "les numéros de ligne sont à jour.")
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
        reste = BUDGET - len(texte)
        if reste <= 200:
            break
        bloc = section if len(section) <= reste else section[:reste] + "\n… (coupé : budget atteint)"
        texte += ("\n\n" if texte else "") + bloc
    return texte
