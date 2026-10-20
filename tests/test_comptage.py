"""Tests du plugin de comptage des tokens du banc."""

import asyncio
from types import SimpleNamespace

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bench.comptage import ComptageTokens


def reponse(entree, sortie, cache=None):
    return LlmResponse(usage_metadata=types.GenerateContentResponseUsageMetadata(
        prompt_token_count=entree, candidates_token_count=sortie, cached_content_token_count=cache))


def test_compte_par_agent_et_totaux():
    comptage = ComptageTokens()
    appels = [("atelier", reponse(1000, 50, 400)), ("diagnostiqueur", reponse(3000, 200)),
              ("atelier", reponse(1200, 30)), ("diagnostiqueur", LlmResponse())]   # sans usage : ignoré
    for agent, r in appels:
        assert asyncio.run(comptage.after_model_callback(
            callback_context=SimpleNamespace(agent_name=agent), llm_response=r)) is None
    assert comptage.par_agent["atelier"] == {"appels_modele": 2, "tokens_entree": 2200,
                                             "tokens_sortie": 80, "tokens_en_cache": 400}
    assert comptage.par_agent["diagnostiqueur"]["appels_modele"] == 1
    assert comptage.totaux() == {"appels_modele": 3, "tokens_entree": 5200,
                                 "tokens_sortie": 280, "tokens_en_cache": 400}
