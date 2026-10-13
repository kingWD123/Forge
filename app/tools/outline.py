"""Outil outline : la carte d'un fichier Python (classes et fonctions, avec leurs lignes).

Permet à l'Atelier de savoir quelle plage lire, au lieu de lire un gros fichier en entier.
"""

import ast
from pathlib import Path

from ._workspace import resolve_in_workspace


def outline(path: str) -> dict:
    """Liste les classes et fonctions d'un fichier Python, avec leurs numéros de ligne.

    Utilise-le avant de lire un gros fichier, puis lis seulement la plage utile avec ReadFile.

    Args:
      path: chemin du fichier .py, relatif au dépôt.

    Returns:
      lines : nombre de lignes du fichier ;
      symbols : une ligne par classe ou fonction, ex. "  def visit_Output  l.1497-1560".
    """
    file = resolve_in_workspace(path)
    if file.suffix != ".py":
        raise ValueError("outline ne lit que les fichiers .py. Pour les autres, utilise search.")
    tree = parse(file)
    symbols = []
    for node, depth in walk_definitions(tree):
        kind = "class" if isinstance(node, ast.ClassDef) else "def"
        symbols.append(f"{'  ' * depth}{kind} {node.name}  l.{node.lineno}-{node.end_lineno}")
    return {"lines": len(file.read_text(encoding="utf-8").splitlines()), "symbols": symbols}


def enclosing_symbol(tree: ast.Module, line: int) -> str:
    """Nom de la fonction (ou classe) la plus intérieure qui contient la ligne, ou ''."""
    name = ""
    for node, _ in walk_definitions(tree):
        if node.lineno <= line <= node.end_lineno:
            name = node.name   # les définitions intérieures viennent après : la dernière gagne
    return name


def parse(file: Path) -> ast.Module:
    try:
        return ast.parse(file.read_text(encoding="utf-8"))
    except SyntaxError as e:
        raise ValueError(f"{file.name} contient une erreur de syntaxe ligne {e.lineno} : {e.msg}") from e


def walk_definitions(node: ast.AST, depth: int = 0):
    """Parcourt classes et fonctions dans l'ordre du fichier, avec leur profondeur d'imbrication."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield child, depth
            yield from walk_definitions(child, depth + 1)
