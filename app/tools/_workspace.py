"""Dépôt de travail de l'Atelier et confinement des chemins."""

import os
from pathlib import Path, PurePosixPath

# Dossiers jamais parcourus par les outils.
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".tox", ".adk",
}


def workspace() -> Path:
    """Dossier du dépôt sur lequel l'Atelier travaille."""
    return Path(os.getenv("FORGE_WORKSPACE") or Path.cwd()).resolve()


def resolve_in_workspace(path: str) -> Path:
    """Résout un chemin relatif au dépôt ; refuse tout chemin qui en sort."""
    root = workspace()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Chemin hors du dépôt de travail : {path}")
    return resolved


def is_secret(path: Path) -> bool:
    """Fichiers exclus par défaut : .env et variantes (.env.local, ...), sauf .env.example."""
    name = path.name
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def est_fichier_de_test(chemin: str) -> bool:
    """Dossier tests/ (ou test/), ou fichier test_*.py, *_test.py, conftest.py."""
    try:
        relatif = PurePosixPath(resolve_in_workspace(chemin).relative_to(workspace()).as_posix())
    except ValueError:
        return False   # hors du dépôt
    nom = relatif.name
    return (any(partie in ("tests", "test") for partie in relatif.parts[:-1])
            or (nom.startswith("test_") and nom.endswith(".py"))
            or nom.endswith("_test.py") or nom == "conftest.py")
