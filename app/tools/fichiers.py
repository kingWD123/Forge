"""ReadFile, WriteFile et Execute : l'Environment Toolset d'ADK, sans son EditFile."""

from google.adk.environment import LocalEnvironment
from google.adk.tools.environment import EnvironmentToolset

from ._workspace import workspace


class EnvironmentSansEditFile(EnvironmentToolset):
    """Environment Toolset d'ADK sans son EditFile, remplacé par notre edit_file."""

    async def get_tools(self, readonly_context=None):
        tools = await super().get_tools(readonly_context)
        return [tool for tool in tools if tool.name != "EditFile"]


def outils_fichiers() -> EnvironmentSansEditFile:
    """ReadFile, WriteFile, Execute, confinés au dépôt de travail."""
    return EnvironmentSansEditFile(
        environment=LocalEnvironment(working_dir=workspace()),
        # Garde-fou large : la vraie coupe (début + fin) est faite par tronquer_sorties.
        max_output_chars=200_000,
    )
