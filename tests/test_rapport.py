"""Un spécialiste rend son rapport par set_model_response, où le schéma est validé."""

import pytest
from google.adk.models import LlmResponse
from google.genai import types
from pydantic import ValidationError

from app.sub_agents.diagnostiqueur.schema import Cause
from app.sub_agents.rapport import rapport_par_set_model_response


def reponse(*parts):
    return LlmResponse(content=types.Content(role="model", parts=list(parts)))


def test_rapport_en_texte_devient_un_appel_valide():
    texte = '```json\n{"statut": "incertain", "nombre_echecs": 3}\n```'
    appel = rapport_par_set_model_response(None, reponse(types.Part(text=texte))).content.parts[0].function_call
    assert appel.name == "set_model_response"
    assert appel.args == {"statut": "incertain", "nombre_echecs": 3}


def test_texte_qui_n_est_pas_du_json_devient_un_appel_vide():
    # La validation dira au modèle quels champs donner.
    appel = rapport_par_set_model_response(None, reponse(types.Part(text="La cause est dans compiler.py")))
    assert appel.content.parts[0].function_call.args == {}


def test_appel_d_outil_et_reponse_vide_inchanges():
    appel = types.Part(function_call=types.FunctionCall(name="run_tests", args={}))
    assert rapport_par_set_model_response(None, reponse(appel)) is None
    assert rapport_par_set_model_response(None, reponse(types.Part(text="  "))) is None


@pytest.fixture
def depot(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "compiler.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))


@pytest.mark.parametrize("lignes", ["1447", "1440-1450", " 12 - 15 "])
def test_lignes_acceptees(depot, lignes):
    assert Cause(chemin="src/compiler.py", lignes=lignes, probleme="p").lignes == lignes.strip()


@pytest.mark.parametrize("lignes", ["Non identifiées spécifiquement", "vers la fin", ""])
def test_lignes_refusees(depot, lignes):
    with pytest.raises(ValidationError, match="n'est pas une ligne"):
        Cause(chemin="src/compiler.py", lignes=lignes, probleme="p")
