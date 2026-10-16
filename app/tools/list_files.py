"""Outil list_files : les fichiers du dépôt qui correspondent à un motif."""

from ._workspace import IGNORED_DIRS, is_secret, workspace


def list_files(motif: str = "**/*", max_results: int = 100) -> dict:
    """Liste les fichiers du dépôt qui correspondent à un motif (glob).

    Args:
      motif: ex. "src/**/*.py", "**/test_*.py", "docs/*". Par défaut tous les fichiers.
      max_results: nombre maximal de chemins renvoyés.

    Returns:
      fichiers : chemins relatifs au dépôt, triés ; total ; truncated (liste coupée).
    """
    if motif.startswith(("/", "\\")) or ".." in motif or ":" in motif:
        raise ValueError("Le motif doit rester dans le dépôt (pas de chemin absolu ni de '..').")
    racine = workspace()
    fichiers = sorted(
        chemin.relative_to(racine).as_posix()
        for chemin in racine.glob(motif)
        if chemin.is_file() and not is_secret(chemin)
        and not any(partie in IGNORED_DIRS for partie in chemin.relative_to(racine).parts)
    )
    return {"fichiers": fichiers[:max_results], "total": len(fichiers),
            "truncated": len(fichiers) > max_results}
