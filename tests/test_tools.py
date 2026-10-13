"""Tests des outils search et run_tests sur un petit dépôt temporaire."""

import textwrap

import pytest

from app.tools import run_tests, search


@pytest.fixture
def depot(tmp_path, monkeypatch):
    (tmp_path / "calc.py").write_text(textwrap.dedent("""\
        def ajouter(a, b):
            return a - b  # bug


        def multiplier(a, b):
            return a * b
    """), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(textwrap.dedent("""\
        from calc import ajouter, multiplier


        def test_ajouter():
            assert ajouter(2, 3) == 5


        def test_multiplier():
            assert multiplier(2, 3) == 6
    """), encoding="utf-8")
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=def ajouter\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignore.py").write_text("def ajouter(): pass\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


def test_search_trouve_les_lignes(depot):
    result = search("def ajouter")
    assert result["matches"] == ["calc.py:1: def ajouter(a, b):"]
    assert result["truncated"] is False


def test_search_ignore_secrets_et_venv(depot):
    matches = search("ajouter")["matches"]
    assert not any(m.startswith((".env", ".venv")) for m in matches)


def test_search_glob_et_limite(depot):
    result = search("ajouter", glob="tests/*.py", max_results=1)
    assert result["total"] == 3  # import, nom du test, assertion
    assert result["truncated"] is True
    assert result["matches"][0].startswith("tests/test_calc.py:")


def test_search_refuse_chemin_hors_depot(depot):
    with pytest.raises(ValueError):
        search("x", path="..")


def test_run_tests_resume_les_echecs(depot):
    result = run_tests()
    assert result["status"] == "failed"
    assert result["counts"] == {"failed": 1, "passed": 1}
    assert len(result["failures"]) == 1
    failure = result["failures"][0]
    assert failure["test"] == "test_ajouter"
    assert "assert -1 == 5" in failure["details"]


def test_run_tests_cible(depot):
    result = run_tests("tests/test_calc.py::test_multiplier")
    assert result["status"] == "passed"
    assert result["counts"] == {"passed": 1}
    assert result["failures"] == []


def test_run_tests_aucun_test(depot):
    result = run_tests(keyword="inexistant")
    assert result["status"] == "no_tests"


def test_run_tests_refuse_chemin_hors_depot(depot):
    with pytest.raises(ValueError):
        run_tests("../ailleurs.py")
