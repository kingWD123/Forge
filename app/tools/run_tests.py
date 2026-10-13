"""Outil run_tests : lance pytest et renvoie un résumé structuré des échecs."""

import os
import re
import subprocess
import sys
from pathlib import Path

from ._workspace import resolve_in_workspace, workspace

_TIMEOUT_SECONDS = 300
_MAX_FAILURES = 10
_MAX_DETAIL_LINES = 30

_EXIT_STATUS = {
    0: "passed",
    1: "failed",
    2: "interrupted",
    3: "internal_error",
    4: "usage_error",
    5: "no_tests",
}


def run_tests(target: str = "", keyword: str = "") -> dict:
    """Lance les tests pytest du dépôt et résume le résultat.

    Args:
      target: fichier, dossier ou test précis, relatif au dépôt
        (ex. "tests/test_billing.py", "tests/test_billing.py::test_total"). Vide = tous les tests.
      keyword: filtre pytest -k (ex. "total and not slow"). Vide = pas de filtre.

    Returns:
      status : passed, failed, no_tests, interrupted, usage_error, internal_error ou timeout ;
      summary : ligne de résumé de pytest (ex. "1 failed, 12 passed in 0.40s") ;
      counts : nombre de tests par résultat ;
      failures : pour chaque test en échec, son nom et la fin de sa trace d'erreur.
    """
    root = workspace()
    cmd = [_python_for(root), "-m", "pytest", "-q", "--tb=short", "-rfE",
           "--no-header", "-p", "no:cacheprovider", "--color=no"]
    if target:
        file_part = target.split("::", 1)[0]
        resolve_in_workspace(file_part)  # refuse un chemin hors du dépôt
        cmd.append(target)
    if keyword:
        cmd += ["-k", keyword]

    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"status": "timeout",
                "summary": f"Tests interrompus après {_TIMEOUT_SECONDS} s.",
                "counts": {}, "failures": []}

    output = proc.stdout + proc.stderr
    result = {
        "status": _EXIT_STATUS.get(proc.returncode, "internal_error"),
        "summary": _summary_line(output),
        "counts": _counts(output),
        "failures": _failures(output),
    }
    if result["status"] in ("usage_error", "internal_error", "interrupted"):
        # Erreur de collecte, d'import ou de commande : la fin de la sortie suffit.
        result["output_tail"] = "\n".join(output.strip().splitlines()[-_MAX_DETAIL_LINES:])
    return result


def _python_for(root: Path) -> str:
    """Python du dépôt (son .venv s'il en a un), sinon celui de l'Atelier."""
    for candidate in (root / ".venv" / "Scripts" / "python.exe",
                      root / ".venv" / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return os.getenv("FORGE_TEST_PYTHON") or sys.executable


def _summary_line(output: str) -> str:
    for line in reversed(output.splitlines()):
        line = line.strip().strip("=").strip()
        if re.search(r"\b(passed|failed|error|errors|skipped|no tests ran)\b", line):
            return line
    return ""


def _counts(output: str) -> dict[str, int]:
    summary = _summary_line(output)
    counts = {}
    for n, kind in re.findall(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|warnings?)", summary):
        kind = {"error": "errors", "warning": "warnings"}.get(kind, kind)
        counts[kind] = int(n)
    return counts


def _failures(output: str) -> list[dict]:
    """Découpe les sections FAILURES/ERRORS de pytest : une entrée par test en échec."""
    lines = output.splitlines()
    failures = []
    in_section = False
    current = None
    for line in lines:
        if re.match(r"^=+ (FAILURES|ERRORS) =+$", line):
            in_section = True
            continue
        if in_section and re.match(r"^=+ .* =+$", line):
            in_section = False  # fin de section (short test summary, ...)
            continue
        if not in_section:
            continue
        header = re.match(r"^_{3,} (.+?) _{3,}$", line)
        if header:
            current = {"test": header.group(1), "lines": []}
            failures.append(current)
        elif current is not None:
            current["lines"].append(line)

    # Messages courts de la section "short test summary info" (FAILED x - message).
    reasons = {}
    for line in lines:
        m = re.match(r"^(FAILED|ERROR) (\S+)(?: - (.*))?$", line)
        if m:
            reasons[m.group(2).split("::")[-1]] = m.group(3) or ""

    result = []
    for f in failures[:_MAX_FAILURES]:
        detail = [l for l in f["lines"] if l.strip()][-_MAX_DETAIL_LINES:]
        entry = {"test": f["test"], "details": "\n".join(detail)}
        short_name = f["test"].split(".")[-1].split(" ")[-1]
        if reasons.get(short_name):
            entry["reason"] = reasons[short_name]
        result.append(entry)
    if len(failures) > _MAX_FAILURES:
        result.append({"test": "…", "details": f"{len(failures) - _MAX_FAILURES} autres échecs non affichés."})
    return result
