"""Un spécialiste rend toujours son rapport par set_model_response, jamais en texte libre.

Avec un output_schema ET des outils, ADK demande au modèle d'appeler set_model_response : c'est
là que le schéma est validé, et une erreur (chemin inexistant, plusieurs fichiers « a ou b »)
revient au modèle pour qu'il corrige. Mais Gemini écrit parfois son rapport JSON directement en
texte : rien ne le valide, l'agent s'arrête, et le rapport faux part tel quel. Sur jinja-009, le
diagnostiqueur a ainsi rendu « runtime.py ou compiler.py », puis jinja2/environment.py (sans
src/), tous deux refusés par le validateur s'il avait été appelé.
"""

import json
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types


def rapport_par_set_model_response(callback_context: CallbackContext,
                                   llm_response: LlmResponse) -> LlmResponse | None:
    """after_model_callback : une réponse finale en texte devient un appel à set_model_response,
    pour que le schéma la valide. Un texte qui n'est pas du JSON devient un appel vide : l'erreur
    de validation dit alors au modèle quels champs donner."""
    parts = (llm_response.content.parts if llm_response.content else None) or []
    if llm_response.partial or any(p.function_call for p in parts):
        return None
    texte = "".join(p.text or "" for p in parts if not p.thought).strip()
    if not texte:
        return None
    texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", texte)
    try:
        args = json.loads(texte)
    except json.JSONDecodeError:
        args = {}
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(
        function_call=types.FunctionCall(name="set_model_response", args=args if isinstance(args, dict) else {}))]))
