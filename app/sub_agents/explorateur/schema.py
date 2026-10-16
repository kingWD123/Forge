"""Format de la réponse de l'explorateur, validé par ADK (output_schema)."""

from typing import Literal

from pydantic import BaseModel, Field


class Emplacement(BaseModel):
    chemin: str = Field(description="Chemin relatif au dépôt, ex. src/jinja2/filters.py")
    lignes: str = Field(description="Plage de lignes lue, ex. 700-730")
    role: str = Field(description="Ce que fait ce code, en une phrase")


class RapportExploration(BaseModel):
    statut: Literal["trouve", "introuvable", "hors_perimetre"] = Field(
        description="trouve ; introuvable (après avoir cherché) ; hors_perimetre (ex. il faut "
                    "lancer les tests : question pour le diagnostiqueur)")
    fichiers: list[Emplacement] = Field(
        default_factory=list, description="5 au plus ; la liste complète pour un inventaire")
    explication: str = Field(description="La réponse à la question, en quelques phrases")
    a_surveiller: list[str] = Field(
        default_factory=list, description="Ce qui pourrait surprendre : cas particuliers, variantes sync/async")
    confiance: Literal["verifie", "suppose"] = Field(
        description="verifie : lu dans le code ; suppose : déduit, à confirmer")
