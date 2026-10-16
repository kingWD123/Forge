"""ReadFile, WriteFile et Execute : l'Environment Toolset d'ADK, sans son EditFile."""

from google.adk.environment import LocalEnvironment
from google.adk.tools.environment import EnvironmentToolset

from ._workspace import workspace


class EnvironmentSansEditFile(EnvironmentToolset):
    """Environment Toolset d'ADK sans son EditFile (remplacé par notre edit_file),
    et en lecture seule si demandé (ReadFile uniquement)."""

    def __init__(self, lecture_seule: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.exclus = {"EditFile", "WriteFile", "Execute"} if lecture_seule else {"EditFile"}

    async def get_tools(self, readonly_context=None):
        tools = await super().get_tools(readonly_context)
        return [tool for tool in tools if tool.name not in self.exclus]


def outils_fichiers(lecture_seule: bool = False) -> EnvironmentSansEditFile:
    """ReadFile, WriteFile, Execute (ou ReadFile seul), confinés au dépôt de travail."""
    return EnvironmentSansEditFile(
        lecture_seule=lecture_seule,
        environment=LocalEnvironment(working_dir=workspace()),
        # Garde-fou large : la vraie coupe (début + fin) est faite par tronquer_sorties.
        max_output_chars=200_000,
    )
