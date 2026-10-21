"""Tests du rédacteur de tests : outils, schéma, écriture limitée aux fichiers de tests."""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.sub_agents.redacteur_tests import redacteur_tests
from app.sub_agents.redacteur_tests.agent import est_fichier_de_test, limiter_aux_tests
from app.sub_agents.redacteur_tests.schema import RapportTests


@pytest.fixture(autouse=True)
def depot(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "meta.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FORGE_PERMISSION_MODE", "auto")
    return tmp_path


def test_outils_et_schema():
    outils = {t.name for t in asyncio.run(redacteur_tests.canonical_tools())}
    # Pas d'Execute : pas de shell pour celui qui n'écrit que des tests.
    assert outils == {"search", "outline", "edit_file", "run_tests", "ReadFile", "WriteFile",
                      "outil_inconnu"}
    assert redacteur_tests.output_schema is RapportTests


def test_rapport_valide():
    rapport = RapportTests.model_validate_json(
        '{"statut": "tests_ecrits", "fichiers": ["tests/test_meta.py"], '
        '"tests": [{"nom": "test_a", "verifie": "renvoie bar"}], "passes": 1, "echoues": 0}')
    assert rapport.bugs == [] and rapport.remarques == ""
    with pytest.raises(ValidationError):
        RapportTests.model_validate_json('{"statut": "fini", "passes": 0, "echoues": 0}')


@pytest.mark.parametrize("chemin", [
    "tests/test_meta.py", "tests/unit/aides.py", "./tests/conftest.py", "tests\\test_meta.py",
    "src/pkg/test_meta.py", "src/pkg/meta_test.py", "conftest.py",
])
def test_fichiers_de_tests_acceptes(chemin):
    assert est_fichier_de_test(chemin)


@pytest.mark.parametrize("chemin", [
    "src/meta.py", "src/tests.py", "testsuite/x.py", "../tests/test_x.py", "setup.py",
])
def test_autres_fichiers_refuses(chemin):
    assert not est_fichier_de_test(chemin)


def appel(nom, chemin):
    return SimpleNamespace(name=nom), {"path": chemin, "content": "x", "old_string": "a", "new_string": "b"}


def test_ecrit_dans_les_tests():
    assert limiter_aux_tests(*appel("WriteFile", "tests/test_meta.py"), SimpleNamespace()) is None


@pytest.mark.parametrize("outil", ["WriteFile", "edit_file"])
def test_refuse_le_code_source(outil):
    reponse = limiter_aux_tests(*appel(outil, "src/meta.py"), SimpleNamespace())
    assert reponse["status"] == "error"
    assert "fichiers de tests" in reponse["error"]


def test_les_lectures_restent_libres():
    assert limiter_aux_tests(SimpleNamespace(name="ReadFile"), {"path": "src/meta.py"}, SimpleNamespace()) is None


def test_autorisations_habituelles_ensuite(depot):
    # Après la limite aux tests, WriteFile reste refusé sur un fichier existant.
    (depot / "tests").mkdir()
    (depot / "tests" / "test_meta.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    reponse = limiter_aux_tests(*appel("WriteFile", "tests/test_meta.py"), SimpleNamespace())
    assert "edit_file" in reponse["error"]
