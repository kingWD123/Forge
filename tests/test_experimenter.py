"""Tests de l'outil experimenter : exécution d'un script dans le dépôt, en lecture seule."""

import importlib

import pytest

from app.tools import experimenter

# Le module (son nom est masqué par la fonction dans app.tools).
module = importlib.import_module("app.tools.experimenter")


@pytest.fixture(autouse=True)
def depot(tmp_path, monkeypatch):
    (tmp_path / "calc.py").write_text("def double(x):\n    return x * 3\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("a\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


def test_execute_et_importe_le_code_du_depot():
    resultat = experimenter("import calc\nprint('double(2) =', calc.double(2))")
    assert resultat == {"status": "ok", "sortie": "double(2) = 6"}


def test_erreur_du_script_renvoyee():
    resultat = experimenter("raise ValueError('cas minimal')")
    assert resultat["status"] == "error" and "ValueError: cas minimal" in resultat["sortie"]


@pytest.mark.parametrize("code", [
    "open('notes.txt', 'w').write('x')",
    "open('nouveau.txt', 'a')",
    "from pathlib import Path\nPath('notes.txt').write_text('x')",
    "import os\nos.remove('notes.txt')",
    "import shutil\nshutil.copy('notes.txt', 'copie.txt')",
])
def test_lecture_seule(depot, code):
    resultat = experimenter(code)
    assert resultat["status"] == "error" and "lecture seule" in resultat["sortie"]
    assert (depot / "notes.txt").read_text(encoding="utf-8") == "a\n"
    assert sorted(p.name for p in depot.iterdir()) == ["calc.py", "notes.txt"]


def test_lire_reste_possible():
    assert experimenter("print(open('notes.txt').read().strip())")["sortie"] == "a"


def test_delai(monkeypatch):
    monkeypatch.setattr(module, "_DELAI_S", 1)
    assert experimenter("import time\ntime.sleep(5)")["status"] == "timeout"
