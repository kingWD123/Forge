"""Tests du diagnostiqueur : lecture seule, schéma, regroupement des échecs."""

import asyncio
import textwrap

import pytest
from pydantic import ValidationError

from app.sub_agents.diagnostiqueur import diagnostiqueur
from app.sub_agents.diagnostiqueur.schema import RapportDiagnostic
from app.tools import regrouper_echecs
from app.tools.regrouper_echecs import normaliser


@pytest.fixture(autouse=True)
def depot(tmp_path, monkeypatch):
    # La cause d'un rapport doit être un fichier qui existe dans le dépôt.
    racine = tmp_path / "depot"   # à part : d'autres tests utilisent tmp_path
    for chemin in ("src/a.py", "src/jinja2/test_x.py", "tests/test_api.py", "conftest.py"):
        (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
        (racine / chemin).write_text("", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(racine))
    return racine


def test_diagnostiqueur_en_lecture_seule():
    outils = {t.name for t in asyncio.run(diagnostiqueur.canonical_tools())}
    assert outils == {"regrouper_echecs", "run_tests", "search", "references", "outline",
                      "git_lecture", "ReadFile", "outil_inconnu", "experimenter"}
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


@pytest.mark.parametrize("chemin", ["tests/test_api.py", "src/jinja2/test_x.py", "conftest.py"])
def test_cause_dans_un_fichier_de_tests_refusee(chemin):
    # Refus renvoyé au diagnostiqueur par ADK (set_model_response), qui doit se corriger.
    with pytest.raises(ValidationError, match="code source"):
        RapportDiagnostic.model_validate_json(
            '{"statut": "cause_trouvee", "nombre_echecs": 74, '
            f'"cause": {{"chemin": "{chemin}", "lignes": "217", "probleme": "espaces"}}, '
            '"preuve": "...", "correction_proposee": "...", "confiance": "verifie"}')


def test_refus_vu_par_le_diagnostiqueur():
    # Le même refus passe par l'outil de réponse finale d'ADK, comme un message d'erreur.
    from google.adk.tools.set_model_response_tool import SetModelResponseTool
    reponse = asyncio.run(SetModelResponseTool(RapportDiagnostic).run_async(args={
        "statut": "cause_trouvee", "nombre_echecs": 74,
        "cause": {"chemin": "tests/test_api.py", "lignes": "217", "probleme": "espaces"},
        "preuve": "...", "correction_proposee": "...", "confiance": "verifie"}, tool_context=None))
    assert "fichier de tests" in reponse["error"]


@pytest.mark.parametrize("chemin", ["src/jinja2/environment.py et src/jinja2/optimizer.py", "src/absent.py",
                                    "../ailleurs.py"])
def test_cause_hors_des_fichiers_du_depot_refusee(chemin):
    with pytest.raises(ValidationError, match="UN seul fichier"):
        RapportDiagnostic.model_validate_json(
            '{"statut": "cause_trouvee", "nombre_echecs": 74, '
            f'"cause": {{"chemin": "{chemin}", "lignes": "20-48", "probleme": "optimisation"}}, '
            '"preuve": "...", "correction_proposee": "...", "confiance": "suppose"}')

