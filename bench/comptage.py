"""Plugin ADK qui compte les appels au modèle et les tokens de TOUS les agents.

Les spécialistes appelés par AgentTool (et les migrateurs lancés par migrer_partout)
tournent dans un runner imbriqué : leurs événements ne remontent pas jusqu'au banc,
mais ils héritent des plugins de l'Atelier. Ce plugin voit donc chaque réponse du modèle,
quel que soit l'agent qui l'a demandée.
"""

from collections import defaultdict
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin

CHAMPS = ("appels_modele", "tokens_entree", "tokens_sortie", "tokens_en_cache")


class ComptageTokens(BasePlugin):
    def __init__(self) -> None:
        super().__init__(name="comptage_tokens")
        self.par_agent: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(CHAMPS, 0))

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> Optional[LlmResponse]:
        usage = llm_response.usage_metadata
        if usage:
            compte = self.par_agent[callback_context.agent_name]
            compte["appels_modele"] += 1
            compte["tokens_entree"] += usage.prompt_token_count or 0
            compte["tokens_sortie"] += usage.candidates_token_count or 0
            # Part des tokens d'entrée servie depuis le cache du modèle (facturée moins cher).
            compte["tokens_en_cache"] += usage.cached_content_token_count or 0
        return None   # la réponse n'est pas modifiée

    def totaux(self) -> dict[str, int]:
        return {champ: sum(c[champ] for c in self.par_agent.values()) for champ in CHAMPS}
