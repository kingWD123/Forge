"""Plugin RedirectionOutilsInconnus : un appel à un outil inexistant devient un appel à
outil_inconnu, qui explique quel outil utiliser (voir app/tools/outil_inconnu.py).

Plugin plutôt que callback : les spécialistes appelés par AgentTool en héritent. Il ne
touche qu'aux agents qui ont outil_inconnu dans leurs outils.
"""

import json
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

OUTIL_INCONNU = "outil_inconnu"


class RedirectionOutilsInconnus(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="redirection_outils_inconnus")
        self._noms_par_agent: dict[str, set[str]] = {}

    async def _noms_des_outils(self, callback_context: CallbackContext) -> set[str]:
        agent = callback_context._invocation_context.agent
        if agent.name not in self._noms_par_agent:
            outils = await agent.canonical_tools(callback_context) if hasattr(agent, "canonical_tools") else []
            self._noms_par_agent[agent.name] = {outil.name for outil in outils}
        return self._noms_par_agent[agent.name]

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        parties = llm_response.content.parts if llm_response.content else None
        if not parties or not any(p.function_call for p in parties):
            return None
        noms = await self._noms_des_outils(callback_context)
        if OUTIL_INCONNU not in noms:
            return None
        modifie = False
        for partie in parties:
            appel = partie.function_call
            # set_model_response : l'outil de réponse finale qu'ADK ajoute aux agents à output_schema.
            if appel and appel.name not in noms and appel.name != "set_model_response":
                partie.function_call = types.FunctionCall(
                    id=appel.id, name=OUTIL_INCONNU,
                    args={"nom": appel.name, "arguments": json.dumps(appel.args or {}, ensure_ascii=False)})
                modifie = True
        return llm_response if modifie else None
