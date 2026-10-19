"""Format de la réponse du rédacteur de tests, validé par ADK (output_schema)."""

from typing import Literal

from pydantic import BaseModel, Field


class TestAjoute(BaseModel):
    nom: str = Field(description="Nom du test, ex. tests/test_meta.py::test_variable_non_declaree")
    verifie: str = Field(description="Le comportement vérifié, en une phrase")


class RapportTests(BaseModel):
    statut: Literal["tests_ecrits", "bug_trouve", "impossible"] = Field(
        description="tests_ecrits : tests écrits et qui passent ; bug_trouve : un test échoue parce que "
                    "le code est faux ; impossible : rien n'a pu être écrit (dis pourquoi dans remarques)")
    fichiers: list[str] = Field(default_factory=list, description="Fichiers de tests créés ou modifiés")
    tests: list[TestAjoute] = Field(default_factory=list, description="Les tests ajoutés")
    passes: int = Field(description="Nombre de tests ajoutés qui passent")
    echoues: int = Field(description="Nombre de tests ajoutés qui échouent")
    bugs: list[str] = Field(
        default_factory=list, description="Pour chaque test en échec : le test, la valeur attendue et "
                                          "la valeur obtenue, et pourquoi c'est le code qui est faux")
    remarques: str = Field(default="", description="Ce qui n'est pas couvert, et pourquoi")
