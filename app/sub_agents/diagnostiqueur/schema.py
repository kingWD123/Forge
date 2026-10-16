"""Format de la réponse du diagnostiqueur, validé par ADK (output_schema)."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Cause(BaseModel):
    chemin: str = Field(description="Fichier du code source en cause, relatif au dépôt")
    lignes: str = Field(description="Ligne ou plage en cause, ex. 1447 ou 1440-1450")
    probleme: str = Field(description="Ce qui est faux dans ce code, en une phrase")


class RapportDiagnostic(BaseModel):
    statut: Literal["cause_trouvee", "incertain", "aucun_echec"] = Field(
        description="cause_trouvee ; incertain (hypothèse non confirmée) ; aucun_echec (tous les tests passent)")
    nombre_echecs: int = Field(description="Nombre de tests en échec")
    cause: Optional[Cause] = Field(default=None, description="La cause dans le code source (pas dans les tests)")
    preuve: str = Field(description="Ce qui montre que c'est la cause : groupe d'échecs, extrait de code")
    correction_proposee: str = Field(description="La modification à faire, précisément")
    tests_concernes: list[str] = Field(default_factory=list, description="Quelques tests en échec, 5 au plus")
    confiance: Literal["verifie", "suppose"] = Field(
        description="verifie : cause lue dans le code et cohérente avec les échecs ; suppose : à confirmer")
