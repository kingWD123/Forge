"""Format de la réponse du diagnostiqueur, validé par ADK (output_schema)."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ...tools._workspace import est_fichier_de_test, resolve_in_workspace


class Cause(BaseModel):
    chemin: str = Field(description="UN fichier du code source en cause, relatif au dépôt")
    lignes: str = Field(description="Ligne ou plage en cause, ex. 1447 ou 1440-1450")
    probleme: str = Field(description="Ce qui est faux dans ce code, en une phrase")

    @field_validator("chemin")
    @classmethod
    def un_fichier_source_qui_existe(cls, chemin: str) -> str:
        # Refus renvoyé au diagnostiqueur par ADK, qui doit alors corriger son rapport.
        try:
            existe = resolve_in_workspace(chemin).is_file()
        except ValueError:
            existe = False
        if not existe:
            raise ValueError(
                f"« {chemin} » n'est pas un fichier du dépôt. Donne UN seul fichier, le chemin exact "
                "relatif au dépôt (ex. src/pkg/module.py) : celui que tu as lu et où est la cause.")
        if est_fichier_de_test(chemin):
            raise ValueError(
                f"{chemin} est un fichier de tests : la cause doit être dans le code source. Un test "
                "qui échoue signale un bug dans le code ; cherche quel code source produit la valeur "
                "reçue (search, references, git_lecture), puis donne ce fichier.")
        return chemin

    @field_validator("lignes")
    @classmethod
    def des_numeros_de_ligne(cls, lignes: str) -> str:
        # « Non identifiées » n'est pas un diagnostic : la ligne se trouve en lisant le code.
        if not re.fullmatch(r"\d+(\s*-\s*\d+)?", lignes.strip()):
            raise ValueError(
                f"« {lignes} » n'est pas une ligne. Donne le numéro de la ligne en cause ou une plage "
                "(ex. 1447 ou 1440-1450), lue avec ReadFile dans le fichier que tu désignes.")
        return lignes.strip()


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
