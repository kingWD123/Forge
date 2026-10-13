"""Outil search : recherche d'un motif dans le dépôt (ripgrep si disponible, sinon Python)."""

import fnmatch
import os
import re
import shutil
import subprocess
from pathlib import Path

from ._workspace import IGNORED_DIRS, is_secret, resolve_in_workspace, workspace

_MAX_LINE_CHARS = 200
_MAX_FILE_BYTES = 1_000_000


def search(
    pattern: str,
    path: str = ".",
    glob: str = "",
    ignore_case: bool = False,
    max_results: int = 50,
) -> dict:
    """Cherche une expression régulière dans les fichiers du dépôt.

    Args:
      pattern: expression régulière à chercher (ex. "def calculer_total", "import requests").
      path: dossier ou fichier où chercher, relatif au dépôt. Par défaut tout le dépôt.
      glob: filtre sur les noms de fichiers (ex. "*.py", "tests/*.py"). Vide = tous.
      ignore_case: True pour ignorer la casse.
      max_results: nombre maximal de lignes renvoyées.

    Returns:
      matches : lignes trouvées au format "chemin:ligne: texte" ;
      total : nombre de correspondances trouvées ;
      truncated : True si la liste a été coupée à max_results.
    """
    root = workspace()
    target = resolve_in_workspace(path)
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Expression régulière invalide : {e}") from e

    if shutil.which("rg"):
        matches = _search_rg(pattern, target, root, glob, ignore_case)
    else:
        matches = _search_python(regex, target, root, glob)

    return {
        "matches": matches[:max_results],
        "total": len(matches),
        "truncated": len(matches) > max_results,
    }


def _format(rel: str, lineno: int, text: str) -> str:
    text = text.strip()
    if len(text) > _MAX_LINE_CHARS:
        text = text[:_MAX_LINE_CHARS] + "…"
    return f"{rel}:{lineno}: {text}"


def _search_rg(pattern: str, target: Path, root: Path, glob: str, ignore_case: bool) -> list[str]:
    cmd = ["rg", "--line-number", "--no-heading", "--color", "never", "--hidden",
           "-g", "!.env", "-g", "!.env.*", "-g", ".env.example"]
    cmd += [arg for d in IGNORED_DIRS for arg in ("-g", f"!{d}/")]
    if glob:
        cmd += ["-g", glob]
    if ignore_case:
        cmd.append("-i")
    # Lancé depuis le dépôt avec un chemin relatif : rg renvoie des chemins relatifs.
    cmd += ["-e", pattern, target.relative_to(root).as_posix() or "."]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60)
    if proc.returncode not in (0, 1):  # 1 = aucune correspondance
        raise RuntimeError(f"ripgrep a échoué : {proc.stderr.strip()}")
    matches = []
    for line in proc.stdout.splitlines():
        m = re.match(r"^(.*?):(\d+):(.*)$", line)
        if m:
            rel = Path(m.group(1)).as_posix().removeprefix("./")
            matches.append(_format(rel, int(m.group(2)), m.group(3)))
    return sorted(matches, key=_sort_key)


def _search_python(regex: re.Pattern, target: Path, root: Path, glob: str) -> list[str]:
    files = [target] if target.is_file() else _walk(target)
    matches = []
    for file in files:
        rel = file.relative_to(root).as_posix()
        if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(file.name, glob)):
            continue
        if is_secret(file) or file.stat().st_size > _MAX_FILE_BYTES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binaire ou illisible
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(_format(rel, lineno, line))
    return sorted(matches, key=_sort_key)


def _walk(directory: Path):
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _sort_key(match: str) -> tuple[str, int]:
    rel, lineno, _ = match.split(":", 2)
    return rel, int(lineno)
