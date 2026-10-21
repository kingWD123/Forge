"""Outils inexistants : réponse claire quand le modèle appelle un outil qu'il n'a pas.

Gemini appelle parfois des outils qu'il connaît d'ailleurs : google:python_interpreter (son
exécution de code intégrée), EditFile (l'outil d'ADK que nous remplaçons par edit_file)...
Sans réponse utile, il recommence en boucle (20 fois de suite sur jinja-009). Le plugin
RedirectionOutilsInconnus remplace ces appels par outil_inconnu, qui dit quel outil utiliser.
"""

import json

# Morceau du nom (en minuscules) -> outil à utiliser à la place.
ALTERNATIVES = (
    ("python", 'Execute, avec command="python -c ..." (ou un script créé avec WriteFile)'),
    ("code_exec", 'Execute, avec command="python -c ..."'),
    ("interpreter", 'Execute, avec command="python -c ..."'),
    ("editfile", "edit_file (old_string = le bloc exact à remplacer, new_string = le nouveau bloc)"),
    ("edit", "edit_file"),
    ("replace", "edit_file"),
    ("write", "WriteFile (nouveau fichier) ou edit_file (fichier existant)"),
    ("read", "ReadFile"),
    ("open", "ReadFile"),
    ("grep", "search"),
    ("find", "search"),
    ("search", "search"),
    ("pytest", "run_tests"),
    ("test", "run_tests"),
    ("bash", "Execute"),
    ("shell", "Execute"),
    ("command", "Execute"),
    ("run", "Execute"),
)


def alternative(nom: str) -> str | None:
    nom = nom.lower().split(":")[-1]
    return next((outil for morceau, outil in ALTERNATIVES if morceau in nom), None)


def outil_inconnu(nom: str, arguments: str = "") -> dict:
    """Réponse à l'appel d'un outil qui n'existe pas. Ne l'appelle pas toi-même.

    Args:
      nom: le nom de l'outil appelé, qui n'existe pas.
      arguments: les arguments de cet appel, en JSON.
    """
    conseil = alternative(nom)
    try:
        recus = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        recus = arguments
    return {
        "status": "error",
        "error": f"L'outil « {nom} » n'existe pas : rien n'a été exécuté. N'appelle que les outils "
                 "de ta liste. " + (f"Utilise plutôt {conseil}." if conseil else
                                    "Choisis l'outil de ta liste qui fait ce que tu veux."),
        "arguments_recus": recus,
    }
