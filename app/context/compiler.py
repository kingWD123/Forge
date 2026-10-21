"""Compilateur de contexte : construit la requête envoyée au modèle à chaque appel.

Appliqué dans un before_model_callback, en suivant l'ordre anti « lost in the middle »
(ce qui compte en tête et à la fin, le reste au milieu) :

1. En tête : le contexte compilé (assemblage.py) — état de la tâche (objectif,
   contraintes épinglées, fichiers modifiés, décisions : etat.py), code des symboles
   visés, tests associés, carte du fichier principal, fichiers liés.
   Les fichiers sont choisis par l'index du dépôt (indexer.py, selection.py).
2. Au milieu : l'historique, allégé par le masquage des sorties d'outils inutiles.
   L'appel reste visible, mais son contenu est remplacé par une ligne :
   - tout de suite : lecture (ReadFile, outline) d'un fichier modifié depuis (contenu
     périmé) et ancien run_tests remplacé par un plus récent ;
   - par paquets : les sorties plus vieilles que les GARDER_RECENTES dernières.
   Masquer par paquets de PAQUET plutôt qu'une sortie de plus à chaque appel garde
   le début de la requête identique d'un appel à l'autre : le modèle peut alors le
   servir depuis son cache, moins cher (même idée qu'OpenCode).
   Filet de sécurité : si la requête dépasse SEUIL_URGENCE caractères, seules les
   GARDER_EN_URGENCE dernières sorties restent entières.
3. À la fin : rappel de l'objectif et de toutes les contraintes épinglées.

Seule la requête est modifiée : l'historique enregistré dans la session reste intact.
Activé par FORGE_CONTEXT=on (configuration B) ; désactivé par défaut (configuration A).
"""

import json
import os

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.genai import types

from ..tools import workspace
from .assemblage import contexte_compile
from .etat import PRIORITE_AU_DERNIER_MESSAGE, fichiers_touches_dans, mettre_a_jour

GARDER_RECENTES = 10       # les N dernières sorties restent entières (valeur de l'étude JetBrains)
PAQUET = 5                 # les vieilles sorties sont masquées 5 par 5
SEUIL_URGENCE = 400_000    # caractères (~100 000 tokens) : au-delà, masquage d'urgence
GARDER_EN_URGENCE = 3
TAILLE_MINIMALE = 300      # on ne masque pas une sortie déjà courte
LECTURES = {"ReadFile", "outline"}
ECRITURES = {"edit_file", "WriteFile"}
# Jamais masquées : les instructions d'une skill ouverte servent jusqu'à la fin de la tâche.
JAMAIS_MASQUEES = {"load_skill"}


def compiler(callback_context: CallbackContext, llm_request: LlmRequest) -> None:
    """before_model_callback : ne renvoie rien, modifie seulement la requête."""
    if os.getenv("FORGE_CONTEXT", "off").lower() != "on":
        return None
    contents = llm_request.contents
    indice = derniere_consigne(contents)
    message = texte_de(contents[indice]) if indice is not None else ""

    # État structuré : gardé dans la session, mis à jour avec le dernier message et les éditions.
    state = callback_context.state if callback_context is not None else {}
    etat = mettre_a_jour(state, message, fichiers_touches_dans(contents, ECRITURES))

    bloc = contexte_compile(workspace(), etat)
    if bloc:
        llm_request.append_instructions([bloc])
    masquer_sorties_inutiles(contents)
    rappeler_objectif(contents, etat)
    return None


def texte_de(content: types.Content) -> str:
    return " ".join(p.text for p in content.parts or [] if p.text).strip()


# ------------------------------------------------------------------ masquage

def masquer_sorties_inutiles(contents: list[types.Content]) -> None:
    appels = {}   # id de l'appel -> (nom de l'outil, arguments)
    sorties = []  # (indice du Content, indice de la part, nom, arguments), dans l'ordre
    for i, content in enumerate(contents):
        for j, part in enumerate(content.parts or []):
            if part.function_call:
                appels[part.function_call.id] = (part.function_call.name, dict(part.function_call.args or {}))
            elif part.function_response:
                nom, args = appels.get(part.function_response.id, (part.function_response.name, {}))
                sorties.append((i, j, nom, args))

    # Frontière : les sorties placées avant elle sont trop vieilles. Elle n'avance que
    # par sauts de PAQUET, sauf en urgence où elle se colle aux dernières sorties.
    if taille(contents) > SEUIL_URGENCE:
        frontiere, raison_age = max(len(sorties) - GARDER_EN_URGENCE, 0), "contexte presque plein"
    else:
        frontiere, raison_age = max(len(sorties) - GARDER_RECENTES, 0) // PAQUET * PAQUET, "ancienne"

    for position, (i, j, nom, args) in enumerate(sorties):
        if nom in JAMAIS_MASQUEES:
            continue
        raison = raison_immediate(nom, args, sorties[position + 1:])
        if not raison and position < frontiere:
            raison = raison_age
        reponse = contents[i].parts[j].function_response
        if raison and len(json.dumps(reponse.response, ensure_ascii=False, default=str)) > TAILLE_MINIMALE:
            remplacer_reponse(contents, i, j, f"[sortie retirée ({raison}) : {decrire(nom, args)}. "
                                              "Relance l'outil si tu en as besoin.]")


def raison_immediate(nom: str, args: dict, suivantes: list) -> str:
    """Une sortie devenue fausse ou remplacée, quel que soit son âge ('' sinon).
    Ces masquages suivent une modification de fichier, qui change déjà le bloc compilé
    en tête : ils ne coûtent rien de plus au cache."""
    if nom in LECTURES:
        fichier = args.get("path")
        if any(n in ECRITURES and a.get("path") == fichier for _, _, n, a in suivantes):
            return "fichier modifié depuis"
    if nom == "run_tests" and any(n == "run_tests" for _, _, n, _ in suivantes):
        return "remplacée par un run_tests plus récent"
    return ""


def taille(contents: list[types.Content]) -> int:
    """Taille approximative de l'historique, en caractères."""
    return sum(len(json.dumps(part.to_json_dict(), ensure_ascii=False, default=str))
               for content in contents for part in content.parts or [])


def remplacer_reponse(contents: list[types.Content], i: int, j: int, texte: str) -> None:
    """Remplace une réponse d'outil par un texte court, sans toucher aux objets de la session
    (on construit un nouveau Content au lieu de modifier l'ancien)."""
    ancienne = contents[i].parts[j].function_response
    nouvelle = types.Part(function_response=types.FunctionResponse(
        id=ancienne.id, name=ancienne.name, response={"resultat": texte}))
    parts = list(contents[i].parts)
    parts[j] = nouvelle
    contents[i] = types.Content(role=contents[i].role, parts=parts)


def decrire(nom: str, args: dict) -> str:
    if nom == "ReadFile":
        plage = f" l.{args['start_line']}-{args.get('end_line', '')}" if args.get("start_line") else ""
        return f"ReadFile {args.get('path', '?')}{plage}"
    if nom in ("outline", "edit_file", "WriteFile"):
        return f"{nom} {args.get('path', '?')}"
    if nom == "search":
        return f"search {args.get('pattern', '?')!r}"
    if nom == "run_tests":
        return f"run_tests {args.get('target') or 'tous les tests'}"
    if nom == "Execute":
        return f"Execute {args.get('command', '?')!r}"
    return nom


# ------------------------------------------------------------------- objectif

def rappeler_objectif(contents: list[types.Content], etat: dict) -> None:
    """Ajoute l'objectif et TOUTES les contraintes épinglées à la fin du dernier message,
    une fois que le travail a commencé (au moins un appel d'outil depuis le dernier message)."""
    consigne_index = derniere_consigne(contents)
    if consigne_index is None or consigne_index == len(contents) - 1 or not etat["objectif"]:
        return
    dernier = contents[-1]
    if dernier.role != "user":
        return
    # Balise explicite : sans elle, le modèle imite ce format et recopie le rappel dans ses réponses.
    lignes = [f"Objectif : {etat['objectif']}"]
    if etat["dernier_message"] and etat["dernier_message"] != etat["objectif"]:
        lignes.append(f"Dernier message de l'utilisateur : {etat['dernier_message']}")
    if etat["contraintes"]:
        lignes.append("Contraintes à respecter : " + " ".join(etat["contraintes"]))
        lignes.append(PRIORITE_AU_DERNIER_MESSAGE)
    texte = ("<rappel_systeme>\nNote automatique pour toi, ne la recopie pas dans ta réponse.\n"
             + "\n".join(lignes) + "\n</rappel_systeme>")
    contents[-1] = types.Content(role="user", parts=[*dernier.parts, types.Part(text=texte)])


def derniere_consigne(contents: list[types.Content]) -> int | None:
    """Indice du dernier message écrit par l'utilisateur (pas une réponse d'outil)."""
    for i in range(len(contents) - 1, -1, -1):
        c = contents[i]
        if c.role == "user" and any(p.text for p in c.parts or []) \
                and not any(p.function_response for p in c.parts or []):
            return i
    return None
