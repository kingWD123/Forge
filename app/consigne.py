"""Ce que l'utilisateur a demandé, lu dans la session : sert aux garde-fous écrits en code
(migrer_partout, protection des tests) pour ne pas dépendre du seul jugement du modèle."""

import re

from google.adk.tools.tool_context import ToolContext

# Demander une migration : renommer, migrer ou remplacer quelque chose partout.
DEMANDE_DE_MIGRATION = re.compile(r"renomm|migr|remplac|partout|rename|replace|everywhere", re.IGNORECASE)
# Demander d'écrire des tests : « écris des tests », « ajoute un test », « mets à jour les tests »...
# « des tests échouent » ou « ne touche pas aux tests » ne comptent pas.
DEMANDE_DE_TESTS = re.compile(
    r"(?:[ée]cri|ajout|compl[eè]t|r[ée]dig|cr[ée]|mets?\s+[àa]\s+jour|adapt|write|add|update)\w*"
    r"\s+(?:\w+\s+){0,3}?tests?\b", re.IGNORECASE)


def messages_utilisateur(tool_context: ToolContext) -> list[str]:
    """Les messages de l'utilisateur dans la session (la consigne et ses précisions)."""
    evenements = getattr(getattr(tool_context, "session", None), "events", None) or []
    textes = [" ".join(p.text or "" for p in (e.content.parts or []))
              for e in evenements if e.author == "user" and e.content]
    if not textes and getattr(tool_context, "user_content", None):
        textes = [" ".join(p.text or "" for p in (tool_context.user_content.parts or []))]
    return textes


def demande(motif: re.Pattern, tool_context: ToolContext) -> bool:
    """Un des messages de l'utilisateur correspond-il au motif ?"""
    return any(motif.search(texte) for texte in messages_utilisateur(tool_context))
