"""Format de la réponse du migrateur, validé par ADK (output_schema)."""

from typing import Literal

from pydantic import BaseModel, Field


class RapportMigration(BaseModel):
    statut: Literal["migre", "partiel", "rien_a_faire"] = Field(
        description="migre : toutes les occurrences traitées ; partiel : il en reste ; "
                    "rien_a_faire : la règle ne s'applique pas à ce fichier")
    fichier: str = Field(description="Le fichier confié, relatif au dépôt")
    modifications: list[str] = Field(
        default_factory=list, description="Une entrée par endroit modifié : « ligne N : ce qui a changé »")
    occurrences_restantes: int = Field(description="Occurrences de l'ancien code encore présentes (0 si migré)")
    incertitudes: list[str] = Field(
        default_factory=list, description="Les cas ambigus que tu n'as pas traités, et pourquoi")
