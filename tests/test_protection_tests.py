"""Tests de la protection des fichiers de tests existants (Atelier) et de la lecture de la consigne."""

from types import SimpleNamespace

import pytest
from google.genai import types

from app.consigne import DEMANDE_DE_MIGRATION, DEMANDE_DE_TESTS, demande
from app.permissions import autoriser_atelier, proteger_les_tests


def session(*messages):
    evenements = [SimpleNamespace(author="user", content=types.Content(role="user", parts=[types.Part(text=m)]))
                  for m in messages]
    return SimpleNamespace(session=SimpleNamespace(events=evenements))


@pytest.mark.parametrize("consigne", [
    "Écris des tests pour meta.py.", "Ajoute un test qui reproduit le bug.", "Mets à jour les tests du filtre.",
    "Complète les tests existants.", "Please write tests for this module.",
])
def test_demande_de_tests_reconnue(consigne):
    assert demande(DEMANDE_DE_TESTS, session(consigne))


@pytest.mark.parametrize("consigne", [
    "Beaucoup de tests échouent depuis le dernier changement. Trouve la cause et corrige-la.",
    "Migre tout le code. Ne touche pas aux tests.", "Corrige le bug, les tests doivent passer.",
])
def test_pas_de_demande_de_tests(consigne):
    assert not demande(DEMANDE_DE_TESTS, session(consigne))


def test_demande_de_migration():
    assert demande(DEMANDE_DE_MIGRATION, session("Renomme internalcode partout."))
    assert not demande(DEMANDE_DE_MIGRATION, session("Corrige le filtre round."))


@pytest.fixture
def depot(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_api.py").write_text("def test_a():\n    assert 1\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "compiler.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FORGE_PERMISSION_MODE", "auto")
    return tmp_path


def edition(chemin, outil="edit_file"):
    return SimpleNamespace(name=outil), {"path": chemin, "old_string": "assert 1", "new_string": "assert 2",
                                         "content": "x"}


CORRIGE_LE_BUG = session("Beaucoup de tests échouent. Trouve la cause et corrige-la.")


def test_refuse_de_modifier_un_test_existant(depot):
    reponse = proteger_les_tests(*edition("tests/test_api.py"), CORRIGE_LE_BUG)
    assert reponse["status"] == "error" and "corrige le code" in reponse["error"]
    # Même refus via le callback complet de l'Atelier, avant toute demande d'accord.
    assert autoriser_atelier(*edition("tests/test_api.py"), CORRIGE_LE_BUG)["status"] == "error"


def test_autorise_si_la_consigne_demande_des_tests(depot):
    assert proteger_les_tests(*edition("tests/test_api.py"), session("Ajoute un test pour ce cas.")) is None


def test_creer_un_nouveau_fichier_de_tests_reste_possible(depot):
    assert proteger_les_tests(*edition("tests/test_nouveau.py", "WriteFile"), CORRIGE_LE_BUG) is None


def test_le_code_source_et_les_lectures_ne_sont_pas_concernes(depot):
    assert proteger_les_tests(*edition("src/compiler.py"), CORRIGE_LE_BUG) is None
    assert proteger_les_tests(SimpleNamespace(name="ReadFile"), {"path": "tests/test_api.py"}, CORRIGE_LE_BUG) is None
