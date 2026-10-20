"""Lance l'Atelier (ou un spécialiste seul) sur une consigne et affiche un résumé JSON
sur la dernière ligne.

Appelé par bench/run.py dans un processus séparé : le dépôt de travail
(FORGE_WORKSPACE) et le mode d'autorisation sont fixés par les variables d'environnement.
Usage : python -m bench.atelier_runner "consigne" [explorateur|diagnostiqueur|migrateur|redacteur_tests]
"""

import asyncio
import json
import sys

from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app
from app.traces import vider_traces
from bench.comptage import ComptageTokens
from app.sub_agents.diagnostiqueur import diagnostiqueur
from app.sub_agents.explorateur import explorateur
from app.sub_agents.migrateur import migrateur
from app.sub_agents.redacteur_tests import redacteur_tests

MAX_APPELS_MODELE = 60
SPECIALISTES = {"explorateur": explorateur, "diagnostiqueur": diagnostiqueur, "migrateur": migrateur,
                "redacteur_tests": redacteur_tests}


async def executer(consigne: str, agent: str = "atelier") -> dict:
    # Compte les tokens de tous les agents, spécialistes compris (ils héritent des plugins).
    comptage = ComptageTokens()
    plugins = [*app.plugins, comptage]
    if agent in SPECIALISTES:
        # Mêmes plugins que dans l'Atelier, dont il hérite quand il y est appelé (AgentTool).
        runner = InMemoryRunner(app=App(name=agent, root_agent=SPECIALISTES[agent], plugins=plugins))
    else:
        runner = InMemoryRunner(app=app.model_copy(update={"plugins": plugins}))
    session = await runner.session_service.create_session(app_name=runner.app_name, user_id="bench")
    message = types.Content(role="user", parts=[types.Part(text=consigne)])

    resultat = {"appels": [], "reponse": ""}
    try:
        async for event in runner.run_async(user_id="bench", session_id=session.id, new_message=message,
                                            run_config=RunConfig(max_llm_calls=MAX_APPELS_MODELE)):
            resultat["appels"] += [appel.name for appel in event.get_function_calls()]
            if event.content and event.content.parts:
                texte = "".join(part.text or "" for part in event.content.parts).strip()
                if texte:
                    resultat["reponse"] = texte
    except Exception as e:  # limite d'appels atteinte, erreur du modèle...
        resultat["erreur"] = f"{type(e).__name__}: {e}"
    # Totaux de tous les agents, et le détail par agent (atelier, diagnostiqueur, migrateur...).
    resultat.update(comptage.totaux())
    resultat["par_agent"] = dict(comptage.par_agent)
    vider_traces()   # le processus s'arrête juste après : envoyer les traces en attente
    return resultat


if __name__ == "__main__":
    print(json.dumps(asyncio.run(executer(*sys.argv[1:3])), ensure_ascii=False))
