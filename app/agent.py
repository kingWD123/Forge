"""L'Atelier : agent principal de FORGE CODE."""

import os
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.adk.skills import load_skills_from_dir
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.skill_toolset import SkillDiscoveryMode, SkillToolset
from google.genai import types

from . import prompt
from app.plugins.indices import IndicesCibles
from app.plugins.verification import VerificationApresEcriture
from .orchestration.migrer_partout import migrer_partout
from .context import compiler, noter_decision, tronquer_sorties
from .permissions import autoriser_atelier
from .sub_agents.diagnostiqueur import diagnostiqueur
from .sub_agents.explorateur import explorateur
from .sub_agents.migrateur import migrateur
from .sub_agents.redacteur_tests import redacteur_tests
from app.plugins.redirection import RedirectionOutilsInconnus
from .tools import edit_file, outil_inconnu, outils_fichiers, outline, run_tests, search

# Configuration C : l'Atelier a ses spécialistes (par défaut). FORGE_SPECIALISTES=off les retire,
# avec la partie du prompt qui en parle : c'est l'agent de code simple des configurations A et B.
SPECIALISTES = os.getenv("FORGE_SPECIALISTES", "on").lower() == "on"

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
    instruction=prompt.atelier_prompt(specialistes=SPECIALISTES),
    tools=[
        # ReadFile, WriteFile, Execute, confinés au dépôt de travail.
        outils_fichiers(),
        search,
        outline,
        edit_file,
        run_tests,
        # Réponse aux appels d'outils inexistants (voir le plugin RedirectionOutilsInconnus).
        outil_inconnu,
        # Configuration B : l'Atelier note ses décisions dans l'état structuré de la tâche.
        *([noter_decision] if os.getenv("FORGE_CONTEXT", "off").lower() == "on" else []),
        *([
            # Spécialistes.
            AgentTool(agent=explorateur),
            AgentTool(agent=diagnostiqueur),
            AgentTool(agent=migrateur),
            # Migration dans tout le dépôt : un migrateur par fichier, lancé par le code.
            migrer_partout,
            AgentTool(agent=redacteur_tests),
            # Skills : procédures longues, chargées seulement quand la situation se présente.
            # Le catalogue (nom + description de chaque skill) est dans le prompt (EAGER) ;
            # leurs instructions n'y entrent qu'au load_skill.
            SkillToolset(skills=load_skills_from_dir(Path(__file__).parent / "skills"),
                         discovery_mode=SkillDiscoveryMode.EAGER, tool_filter=["load_skill"]),
            # La mécanique de la forge (évaluateur, forgeron, banc d'essai, vérificateur) sera
            # branchée aux semaines 7 et 8 : un outil exposé mais interdit détourne le modèle.
        ] if SPECIALISTES else []),
    ],
    # Tests existants protégés ; lectures libres ; écritures et commandes soumises à l'accord de l'utilisateur.
    before_tool_callback=autoriser_atelier,
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
    plugins=[ReflectAndRetryToolPlugin(max_retries=3, throw_exception_if_retry_exceeded=False),
             # Un appel à un outil qui n'existe pas devient un appel à outil_inconnu.
             RedirectionOutilsInconnus(),
             # Indice ajouté à la sortie d'un outil quand une délégation s'impose.
             IndicesCibles(),
             # Juste après une modification d'un module : s'importe-t-il encore ?
             VerificationApresEcriture()],
)
