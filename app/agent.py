"""L'Atelier : agent principal de FORGE CODE."""

import os

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from . import prompt
from .context import compiler, noter_decision, tronquer_sorties
from .permissions import autoriser
from .sub_agents.banc_essai import banc_essai_agent
from .sub_agents.diagnostiqueur import diagnostiqueur
from .sub_agents.evaluateur import evaluateur_agent
from .sub_agents.explorateur import explorateur
from .sub_agents.forgeron import forgeron_agent
from .sub_agents.migrateur import migrateur
from .sub_agents.redacteur_tests import redacteur_tests
from .sub_agents.verificateur import verificateur_agent
from .tools import edit_file, outils_fichiers, outline, run_tests, search

atelier = LlmAgent(
    model=Gemini(
        model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
        retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2, max_delay=60),
    ),
    name="atelier",
    description=(
        "Agent de code en terminal : lit, cherche, édite, exécute et teste le"
        " code du dépôt, et délègue aux sous-agents quand la tâche dépasse son"
        " contexte."
    ),
    instruction=prompt.ATELIER_PROMPT,
    tools=[
        # ReadFile, WriteFile, Execute, confinés au dépôt de travail.
        outils_fichiers(),
        search,
        outline,
        edit_file,
        run_tests,
        # Configuration B : l'Atelier note ses décisions dans l'état structuré de la tâche.
        *([noter_decision] if os.getenv("FORGE_CONTEXT", "off").lower() == "on" else []),
        # Spécialistes.
        AgentTool(agent=explorateur),
        AgentTool(agent=diagnostiqueur),
        AgentTool(agent=migrateur),
        AgentTool(agent=redacteur_tests),
        # Mécanique de la forge (semaines 7 et 8).
        AgentTool(agent=evaluateur_agent),
        AgentTool(agent=forgeron_agent),
        AgentTool(agent=banc_essai_agent),
        AgentTool(agent=verificateur_agent),
    ],
    # Lectures libres ; écritures et commandes soumises à l'accord de l'utilisateur.
    before_tool_callback=autoriser,
    # Sorties trop longues coupées en gardant le début et la fin.
    after_tool_callback=tronquer_sorties,
    # Compilateur de contexte (FORGE_CONTEXT=on) : allège la requête avant chaque appel au modèle.
    before_model_callback=compiler,
)

root_agent = atelier

# Quand un outil lève une erreur (bloc introuvable, syntaxe cassée...), ce plugin
# renvoie l'erreur au modèle avec des consignes pour corriger son appel (3 essais).
app = App(
    name="app",
    root_agent=atelier,
    plugins=[ReflectAndRetryToolPlugin(max_retries=3, throw_exception_if_retry_exceeded=False)],
)
