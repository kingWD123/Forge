"""Lance l'Atelier sur une consigne et affiche un résumé JSON sur la dernière ligne.

Appelé par bench/run.py dans un processus séparé : le dépôt de travail
(FORGE_WORKSPACE) et le mode d'autorisation sont fixés par les variables d'environnement.
"""

import asyncio
import json
import sys

from google.adk.agents.run_config import RunConfig
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agent import app

MAX_APPELS_MODELE = 60


async def executer(consigne: str) -> dict:
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name=app.name, user_id="bench")
    message = types.Content(role="user", parts=[types.Part(text=consigne)])

    resultat = {"appels": [], "appels_modele": 0, "tokens_entree": 0, "tokens_sortie": 0, "reponse": ""}
    try:
        async for event in runner.run_async(user_id="bench", session_id=session.id, new_message=message,
                                            run_config=RunConfig(max_llm_calls=MAX_APPELS_MODELE)):
            resultat["appels"] += [appel.name for appel in event.get_function_calls()]
            if event.usage_metadata:
                resultat["appels_modele"] += 1
                resultat["tokens_entree"] += event.usage_metadata.prompt_token_count or 0
                resultat["tokens_sortie"] += event.usage_metadata.candidates_token_count or 0
            if event.content and event.content.parts:
                texte = "".join(part.text or "" for part in event.content.parts).strip()
                if texte:
                    resultat["reponse"] = texte
    except Exception as e:  # limite d'appels atteinte, erreur du modèle...
        resultat["erreur"] = f"{type(e).__name__}: {e}"
    return resultat


if __name__ == "__main__":
    print(json.dumps(asyncio.run(executer(sys.argv[1])), ensure_ascii=False))
