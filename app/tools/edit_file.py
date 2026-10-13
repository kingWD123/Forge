"""Outil edit_file : remplace un bloc de texte dans un fichier du dépôt.

Remplace l'EditFile d'ADK pour corriger deux défauts observés :
1. Indentation doublée : le modèle copie l'ancien bloc sans son indentation,
   mais écrit le nouveau bloc avec. On détecte ce cas et on ne double pas.
2. Fins de ligne : dans un fichier Windows (CRLF), le texte inséré garde
   les fins de ligne du fichier.

Et un garde-fou : une édition qui casserait la syntaxe d'un fichier Python est refusée.
"""

import difflib

from ._workspace import is_secret, resolve_in_workspace, workspace


def edit_file(path: str, old_string: str, new_string: str) -> dict:
    """Remplace un bloc de texte dans un fichier existant du dépôt.

    Copie old_string tel qu'il apparaît dans le fichier, avec son indentation.
    Il doit apparaître une seule fois : ajoute des lignes voisines si besoin.
    Pour créer un fichier, utilise WriteFile.

    Args:
      path: chemin du fichier, relatif au dépôt.
      old_string: bloc exact à remplacer.
      new_string: texte de remplacement.

    Returns:
      status "ok" et le diff appliqué. En cas d'erreur, rien n'est écrit.
    """
    file, new_content = prepare_edit(path, old_string, new_string)
    file.write_bytes(new_content.encode("utf-8"))
    return {"status": "ok", "diff": make_diff(path, old_string, new_string)}


def prepare_edit(path: str, old: str, new: str):
    """Calcule le nouveau contenu sans rien écrire. Lève ValueError si l'édition est impossible."""
    file = resolve_in_workspace(path)
    if is_secret(file):
        raise ValueError(f"{path} contient des secrets : modification interdite.")
    if not file.is_file():
        raise ValueError(f"Fichier introuvable : {path}. Pour créer un fichier, utilise WriteFile.")
    if not old:
        raise ValueError("old_string est vide.")

    # On travaille avec des fins de ligne "\n", on remettra celles du fichier à la fin.
    content = file.read_bytes().decode("utf-8")
    crlf = "\r\n" in content
    content = content.replace("\r\n", "\n")
    old = old.replace("\r\n", "\n")
    new = new.replace("\r\n", "\n")

    count = content.count(old)
    if count == 0:
        raise ValueError("old_string introuvable. Relis le fichier et copie le bloc exact.")
    if count > 1:
        raise ValueError(f"old_string apparaît {count} fois. Ajoute des lignes voisines.")

    start = content.index(old)
    end = start + len(old)
    start = fix_doubled_indent(content, start, old, new)
    new_content = content[:start] + new + content[end:]

    if path.endswith(".py"):
        check_python_syntax(path, content, new_content)

    if crlf:
        new_content = new_content.replace("\n", "\r\n")
    return file, new_content


def fix_doubled_indent(content: str, start: int, old: str, new: str) -> int:
    """Renvoie la position où commencer le remplacement.

    Exemple : la ligne est "    return x" et le modèle envoie
    old = "return x" (sans indentation) et new = "    return y" (avec).
    Remplacer à partir de "return" donnerait "        return y".
    Dans ce cas, on remplace depuis le début de la ligne.
    """
    line_start = content.rfind("\n", 0, start) + 1
    before = content[line_start:start]          # ce qui précède old sur sa ligne
    line_indent = before + indent_of(old)       # indentation réelle de la ligne
    old_starts_mid_indent = before != "" and before.strip() == ""
    if old_starts_mid_indent and indent_of(new) == line_indent:
        return line_start
    return start


def indent_of(text: str) -> str:
    """Espaces et tabulations au début de la première ligne."""
    first_line = text.split("\n", 1)[0]
    return first_line[: len(first_line) - len(first_line.lstrip())]


def check_python_syntax(path: str, before: str, after: str) -> None:
    """Refuse l'édition si elle rend invalide un fichier Python qui était valide."""
    try:
        compile(before, path, "exec")
    except SyntaxError:
        return  # déjà invalide avant : on laisse l'agent tenter de le réparer
    try:
        compile(after, path, "exec")
    except SyntaxError as e:
        raise ValueError(
            f"Édition refusée : syntaxe Python cassée ligne {e.lineno} ({e.msg}). "
            "Vérifie l'indentation de new_string."
        ) from e


def make_diff(path: str, old: str, new: str) -> str:
    """Diff lisible entre l'ancien et le nouveau bloc."""
    lines = difflib.unified_diff(old.splitlines(), new.splitlines(),
                                 f"a/{path}", f"b/{path}", lineterm="")
    return "\n".join(lines)
