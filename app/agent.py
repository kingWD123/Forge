"""L'Atelier : agent principal de FORGE CODE."""

import os

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.environment import LocalEnvironment
from google.adk.models import Gemini
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.environment import EnvironmentToolset
from google.genai import types

from . import prompt
from .permissions import autoriser
from .tools import edit_file, outline, run_tests, search, workspace
from .sub_agents.banc_essai import banc_essai_agent
from .sub_agents.evaluateur import evaluateur_agent
from .sub_agents.forgeron import forgeron_agent
from .sub_agents.verificateur import verificateur_agent


class EnvironmentSansEditFile(EnvironmentToolset):
    """Environment Toolset d'ADK sans son EditFile, remplacé par notre edit_file."""

    async def get_tools(self, readonly_context=None):
        tools = await super().get_tools(readonly_context)
        return [tool for tool in tools if tool.name != "EditFile"]


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
        EnvironmentSansEditFile(
            environment=LocalEnvironment(working_dir=workspace()),
            # Environ 200 lignes par lecture : on lit des plages ciblées, pas des fichiers entiers.
            max_output_chars=8_000,
        ),
        search,
        outline,
        edit_file,
        run_tests,
        AgentTool(agent=evaluateur_agent),
        AgentTool(agent=forgeron_agent),
        AgentTool(agent=banc_essai_agent),
        AgentTool(agent=verificateur_agent),
    ],
    # Lectures libres ; écritures et commandes soumises à l'accord de l'utilisateur.
    before_tool_callback=autoriser,
)

root_agent = atelier

# Quand un outil lève une erreur (bloc introuvable, syntaxe cassée...), ce plugin
# renvoie l'erreur au modèle avec des consignes pour corriger son appel (3 essais).
app = App(
    name="app",
    root_agent=atelier,
    plugins=[ReflectAndRetryToolPlugin(max_retries=3, throw_exception_if_retry_exceeded=False)],
)
