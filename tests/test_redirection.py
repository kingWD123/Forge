"""Tests de la redirection des appels d'outils inexistants vers outil_inconnu."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.plugins.redirection import RedirectionOutilsInconnus
from app.tools.outil_inconnu import alternative, outil_inconnu


@pytest.mark.parametrize("nom, attendu", [
    ("google:python_interpreter", "Execute"), ("EditFile", "edit_file"), ("grep", "search"),
    ("pytest", "run_tests"), ("read_file", "ReadFile"),
])
def test_alternative(nom, attendu):
    assert alternative(nom).startswith(attendu)


def test_outil_inconnu_explique_quoi_faire():
    reponse = outil_inconnu("google:python_interpreter", json.dumps({"code": "print(1)"}))
    assert reponse["status"] == "error"
    assert "n'existe pas" in reponse["error"] and "Execute" in reponse["error"]
    assert reponse["arguments_recus"] == {"code": "print(1)"}
    assert "Choisis l'outil" in outil_inconnu("teleporter")["error"]
    assert outil_inconnu("x", "pas du json")["arguments_recus"] == "pas du json"


def contexte(*noms_outils, nom_agent="atelier"):
    agent = SimpleNamespace(name=nom_agent)

    async def canonical_tools(_ctx):
        return [SimpleNamespace(name=n) for n in noms_outils]

    agent.canonical_tools = canonical_tools
    return SimpleNamespace(_invocation_context=SimpleNamespace(agent=agent))


def reponse(*appels):
    return LlmResponse(content=types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(id=f"id{i}", name=n, args=a)) for i, (n, a) in enumerate(appels)]))


def rediriger(ctx, r):
    return asyncio.run(RedirectionOutilsInconnus().after_model_callback(callback_context=ctx, llm_response=r))


def test_redirige_l_outil_inexistant_et_garde_les_autres():
    r = reponse(("google:python_interpreter", {"code": "print(1)"}), ("search", {"pattern": "x"}))
    modifiee = rediriger(contexte("search", "outil_inconnu"), r)
    appel, garde = (p.function_call for p in modifiee.content.parts)
    assert appel.name == "outil_inconnu" and appel.id == "id0"   # même id : la réponse s'y rattache
    assert appel.args["nom"] == "google:python_interpreter"
    assert json.loads(appel.args["arguments"]) == {"code": "print(1)"}
    assert garde.name == "search"


def test_ne_touche_pas_aux_appels_valides_ni_a_la_reponse_finale():
    r = reponse(("search", {}), ("set_model_response", {"statut": "x"}))
    assert rediriger(contexte("search", "outil_inconnu"), r) is None


def test_agent_sans_outil_inconnu_non_modifie():
    assert rediriger(contexte("search"), reponse(("EditFile", {}),)) is None


def test_texte_sans_appel():
    texte = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="fini")]))
    assert rediriger(contexte("outil_inconnu"), texte) is None
