"""Tests du diagnostiqueur : lecture seule, schéma, regroupement des échecs."""

import asyncio
import textwrap

import pytest
from pydantic import ValidationError

from app.sub_agents.diagnostiqueur import diagnostiqueur
from app.sub_agents.diagnostiqueur.schema import RapportDiagnostic
from app.tools import regrouper_echecs
from app.tools.regrouper_echecs import normaliser


def test_diagnostiqueur_en_lecture_seule():
    outils = {t.name for t in asyncio.run(diagnostiqueur.canonical_tools())}
    assert outils == {"regrouper_echecs", "run_tests", "search", "references", "outline",
                      "git_lecture", "ReadFile"}
    assert diagnostiqueur.output_schema is RapportDiagnostic


def test_rapport_valide():
    rapport = RapportDiagnostic.model_validate_json(
        '{"statut": "cause_trouvee", "nombre_echecs": 96, '
        '"cause": {"chemin": "src/a.py", "lignes": "12", "probleme": "strip en trop"}, '
        '"preuve": "...", "correction_proposee": "...", "confiance": "verifie"}')
    assert rapport.cause.chemin == "src/a.py"
    with pytest.raises(ValidationError):   # statut inconnu : refusé
        RapportDiagnostic.model_validate_json(
            '{"statut": "peut-etre", "nombre_echecs": 0, "preuve": "", "correction_proposee": "", '
            '"confiance": "verifie"}')


def test_normaliser_rapproche_les_messages_de_meme_nature():
    assert normaliser("AssertionError: assert 'a b' == 'ab'") == normaliser("AssertionError: assert 'x y' == 'xy'")
    assert normaliser("assert 3 == 4") == "assert N == N"


def test_regrouper_echecs(tmp_path, monkeypatch):
    (tmp_path / "calc.py").write_text("def nettoyer(s):\n    return s.strip() + '!'\n", encoding="utf-8")
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(textwrap.dedent("""\
        from calc import nettoyer

        def test_un():
            assert nettoyer(" a ") == "a"

        def test_deux():
            assert nettoyer("b") == "b"

        def test_autre():
            assert 1 == 2
    """), encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    resultat = regrouper_echecs()
    assert resultat["total_echecs"] == 3
    gros = resultat["groupes"][0]
    assert gros["nombre"] == 2 and gros["fichiers_de_tests"] == ["tests/test_a.py"]   # même cause
    assert resultat["groupes"][1]["nombre"] == 1
