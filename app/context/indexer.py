"""Indexation du dépôt : pour chaque fichier Python, ses symboles (classes, fonctions)
avec signature et lignes, et les fichiers du dépôt qu'il importe.

Utilise le module ast de Python (le banc ne contient que du Python) ; tree-sitter
pourra le remplacer pour d'autres langages sans changer le reste du Compilateur.
Chaque fichier n'est réanalysé que s'il a changé depuis la dernière indexation.
"""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..tools._workspace import IGNORED_DIRS


@dataclass(frozen=True)
class Symbole:
    nom: str
    signature: str      # ex. "def do_round(value, precision=0, method='common')"
    debut: int
    fin: int
    doc: str            # première ligne de la docstring


@dataclass
class Fichier:
    chemin: str                                     # relatif au dépôt, ex. "src/jinja2/filters.py"
    module: str                                     # ex. "jinja2.filters"
    symboles: list[Symbole] = field(default_factory=list)
    modules_importes: set[str] = field(default_factory=set)  # tels qu'écrits : "os", "jinja2.utils"
    imports: set[str] = field(default_factory=set)           # chemins des fichiers du dépôt importés


@dataclass
class Index:
    fichiers: dict[str, Fichier]

    def importe_par(self, chemin: str) -> list[str]:
        """Fichiers du dépôt qui importent ce fichier."""
        return sorted(f.chemin for f in self.fichiers.values() if chemin in f.imports)


_cache: dict[Path, tuple[float, Fichier]] = {}   # fichier -> (date de modification, analyse)


def indexer(racine: Path) -> Index:
    fichiers = {}
    for chemin in fichiers_python(racine):
        rel = chemin.relative_to(racine).as_posix()
        date = chemin.stat().st_mtime
        if chemin not in _cache or _cache[chemin][0] != date:
            _cache[chemin] = (date, analyser(chemin, rel))
        fichiers[rel] = _cache[chemin][1]
    resoudre_imports(fichiers)
    return Index(fichiers)


def fichiers_python(racine: Path):
    for dossier, sous_dossiers, noms in os.walk(racine):
        sous_dossiers[:] = sorted(d for d in sous_dossiers if d not in IGNORED_DIRS and not d.startswith("."))
        for nom in sorted(noms):
            if nom.endswith(".py"):
                yield Path(dossier) / nom


def nom_de_module(rel: str) -> str:
    """'src/jinja2/filters.py' -> 'jinja2.filters' ; '.../__init__.py' -> le paquet."""
    parties = rel.removesuffix(".py").split("/")
    if parties[0] == "src":
        parties = parties[1:]
    if parties[-1] == "__init__":
        parties = parties[:-1]
    return ".".join(parties)


def analyser(chemin: Path, rel: str) -> Fichier:
    fichier = Fichier(chemin=rel, module=nom_de_module(rel))
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return fichier   # fichier invalide : indexé sans symboles

    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fichier.symboles.append(Symbole(noeud.name, signature(noeud), noeud.lineno,
                                            noeud.end_lineno, premiere_ligne_doc(noeud)))
        elif isinstance(noeud, ast.Import):
            fichier.modules_importes.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            fichier.modules_importes.add(module_absolu(fichier.module, rel, noeud))
    fichier.symboles.sort(key=lambda s: s.debut)
    return fichier


def signature(noeud) -> str:
    """Signature compacte, sans annotations de types : def do_round(value, precision=0, method='common')."""
    if isinstance(noeud, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in noeud.bases)
        return f"class {noeud.name}({bases})" if bases else f"class {noeud.name}"
    prefixe = "async def" if isinstance(noeud, ast.AsyncFunctionDef) else "def"
    arguments = noeud.args
    for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                     arguments.vararg, arguments.kwarg]:
        if argument is not None:
            argument.annotation = None
    return f"{prefixe} {noeud.name}({ast.unparse(arguments)})"


def premiere_ligne_doc(noeud) -> str:
    doc = ast.get_docstring(noeud) or ""
    return doc.strip().split("\n", 1)[0][:120]


def module_absolu(module: str, rel: str, noeud: ast.ImportFrom) -> str:
    """Transforme `from .utils import x` en 'jinja2.utils'."""
    if not noeud.level:
        return noeud.module or ""
    paquet = module.split(".")
    if not rel.endswith("__init__.py"):
        paquet = paquet[:-1]                  # un module : son paquet est le dossier parent
    paquet = paquet[: len(paquet) - (noeud.level - 1)]
    return ".".join([*paquet, noeud.module] if noeud.module else paquet)


def resoudre_imports(fichiers: dict[str, Fichier]) -> None:
    """Traduit les modules importés en chemins de fichiers du dépôt
    (les imports extérieurs au dépôt, comme `os`, sont ignorés)."""
    par_module = {f.module: f.chemin for f in fichiers.values()}
    for f in fichiers.values():
        f.imports = {par_module[m] for m in f.modules_importes
                     if m in par_module and par_module[m] != f.chemin}
