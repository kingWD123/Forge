"""Tests du migrateur : outils, schéma, limite au fichier confié."""

import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types
from pydantic import ValidationError

from app.sub_agents.migrateur import migrateur
from app.sub_agents.migrateur.agent import limiter_au_fichier_confie
from app.sub_agents.migrateur.schema import RapportMigration


def test_outils_et_schema():
    outils = {t.name for t in asyncio.run(migrateur.canonical_tools())}
    assert outils == {"search", "outline", "edit_file", "ReadFile", "outil_inconnu"}
    assert migrateur.output_schema is RapportMigration


def test_rapport_valide():
    rapport = RapportMigration.model_validate_json(
        '{"statut": "migre", "fichier": "src/a.py", "modifications": ["ligne 3 : x -> y"], '
        '"occurrences_restantes": 0}')
    assert rapport.incertitudes == []
    with pytest.raises(ValidationError):
        RapportMigration.model_validate_json('{"statut": "fini", "fichier": "a", "occurrences_restantes": 0}')


def contexte(demande):
    return SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=demande)]))


def edition(chemin):
    return SimpleNamespace(name="edit_file"), {"path": chemin, "old_string": "a", "new_string": "b"}


@pytest.fixture(autouse=True)
def mode_auto(monkeypatch):
    monkeypatch.setenv("FORGE_PERMISSION_MODE", "auto")


def test_modifie_le_fichier_confie():
    outil, args = edition("src/jinja2/runtime.py")
    demande = "Dans src/jinja2/runtime.py, renomme internalcode en mark_internal."
    assert limiter_au_fichier_confie(outil, args, contexte(demande)) is None


def test_refuse_un_autre_fichier():
    outil, args = edition("src/jinja2/loaders.py")
    demande = "Dans src/jinja2/runtime.py, renomme internalcode en mark_internal."
    assert "que le fichier qui t'a été confié" in limiter_au_fichier_confie(outil, args, contexte(demande))["error"]


def test_les_lectures_restent_libres():
    lecture = SimpleNamespace(name="ReadFile")
    assert limiter_au_fichier_confie(lecture, {"path": "src/autre.py"}, contexte("src/a.py")) is None
