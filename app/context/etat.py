"""État structuré de la tâche : la mémoire de travail de l'Atelier (dossier, semaines 3 et 5).

Quatre rubriques, gardées dans l'état de la session ADK plutôt que dans l'historique :
  objectif           la tâche en cours (un simple « continue » ne l'efface pas)
  contraintes        épinglées : celles de TOUS les messages, accumulées, jamais perdues
  fichiers_touches   fichiers réellement modifiés (éditions réussies seulement)
  decisions          ce que l'Atelier a établi, noté avec l'outil noter_decision

Le Compilateur met l'état à jour avant chaque appel au modèle et l'affiche en tête de
la requête : une consigne donnée au début reste visible 40 étapes plus tard.
L'état ne dure que le temps de la session : ce n'est pas une mémoire à long terme.
"""

import re

from google.adk.tools.tool_context import ToolContext
from google.genai import types

CLE = "etat_structure"
MAX_DECISIONS = 10

# Les contraintes restent valables, sauf si l'utilisateur en décide explicitement autrement.
PRIORITE_AU_DERNIER_MESSAGE = (
    "Si le dernier message de l'utilisateur demande explicitement autre chose qu'une "
    "contrainte, son dernier message prime : fais-le et signale que tu lèves la contrainte.")

# Messages qui relancent le travail sans changer d'objectif.
_RELANCE = re.compile(r"^\W*(ok|oui|d'accord|vas[- ]y|go|continue|continuer|poursuis|encore|"
                      r"la suite|suivant|merci)\b", re.IGNORECASE)


_MOTS_DE_CONTRAINTE = re.compile(
    r"\bne\b|\bn['’]|\bsans\b|\bjamais\b|\binterdit|\bcontrainte|\buniquement\b|\bseulement\b"
    r"|\bdoit\b|\bdoivent\b", re.IGNORECASE)


def extraire_contraintes(message: str) -> list[str]:
    """Les phrases d'un message qui posent une règle (« ne modifie que... », « sans... »)."""
    phrases = re.split(r"(?<=[.!?])\s+|\n", message)
    return [p.strip() for p in phrases if p.strip() and _MOTS_DE_CONTRAINTE.search(p)]


def etat_vide() -> dict:
    return {"objectif": "", "contraintes": [], "fichiers_touches": [], "decisions": [],
            "dernier_message": ""}


def lire(state) -> dict:
    return {**etat_vide(), **(state.get(CLE) or {})}


def mettre_a_jour(state, message: str, fichiers: list[str]) -> dict:
    """Intègre le dernier message de l'utilisateur et les fichiers modifiés, puis enregistre."""
    etat = lire(state)
    if message and message != etat["dernier_message"]:   # un nouveau message de l'utilisateur
        etat["dernier_message"] = message
        if not etat["objectif"] or not est_une_relance(message):
            etat["objectif"] = message
        for contrainte in extraire_contraintes(message):
            if contrainte not in etat["contraintes"]:
                etat["contraintes"].append(contrainte)
    for fichier in fichiers:
        if fichier not in etat["fichiers_touches"]:
            etat["fichiers_touches"].append(fichier)
    state[CLE] = etat   # réaffecter : ADK n'enregistre que les clés réaffectées
    return etat


def est_une_relance(message: str) -> bool:
    """« Ok, continue avec le fichier suivant » relance le travail ; ce n'est pas une nouvelle tâche."""
    return len(message.split()) <= 8 and bool(_RELANCE.search(message))


def fichiers_touches_dans(contents: list[types.Content], outils_ecriture: set[str]) -> list[str]:
    """Fichiers modifiés avec succès : un appel d'écriture dont la réponse n'est pas une erreur."""
    chemins = {}   # id de l'appel -> chemin
    touches = []
    for content in contents:
        for part in content.parts or []:
            appel, reponse = part.function_call, part.function_response
            if appel and appel.name in outils_ecriture and appel.args and appel.args.get("path"):
                chemins[appel.id] = appel.args["path"]
            elif reponse and reponse.id in chemins:
                resultat = reponse.response or {}
                if "error" not in resultat and resultat.get("status") != "error":
                    touches.append(chemins[reponse.id])
    return list(dict.fromkeys(touches))


def noter_decision(decision: str, tool_context: ToolContext) -> dict:
    """Note une décision ou un fait établi, pour ne pas le perdre quand l'historique s'allonge.

    Utilise-le quand tu as compris quelque chose d'important pour la suite :
    la cause d'un bug, un choix de conception, l'ordre dans lequel procéder.
    Les décisions notées restent affichées en tête de ton contexte.

    Args:
      decision: une phrase courte, ex. "La cause est le .strip() dans compiler.py".
    """
    etat = lire(tool_context.state)
    etat["decisions"] = [*etat["decisions"], decision.strip()][-MAX_DECISIONS:]
    tool_context.state[CLE] = etat
    return {"status": "ok", "decisions": etat["decisions"]}


def afficher(etat: dict) -> str:
    """Section « État de la tâche », placée en tout premier dans le contexte compilé."""
    if not etat["objectif"]:
        return ""
    lignes = ["## État de la tâche", f"Objectif : {etat['objectif']}"]
    if etat["dernier_message"] and etat["dernier_message"] != etat["objectif"]:
        lignes.append(f"Dernier message de l'utilisateur : {etat['dernier_message']}")
    if etat["contraintes"]:
        lignes += ["Contraintes à respecter (toujours valables) :", *[f"- {c}" for c in etat["contraintes"]],
                   PRIORITE_AU_DERNIER_MESSAGE]
    if etat["fichiers_touches"]:
        lignes.append("Fichiers déjà modifiés : " + ", ".join(etat["fichiers_touches"]))
    if etat["decisions"]:
        lignes += ["Décisions prises :", *[f"- {d}" for d in etat["decisions"]]]
    lignes.append("(Quand tu établis un fait important, note-le avec noter_decision : "
                  "il restera ici même quand l'historique sera allégé.)")
    return "\n".join(lignes)
