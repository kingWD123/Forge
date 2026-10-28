"""Fiche d'un sous-agent forgé : .forge/agents/<name>.yaml, validée avant tout chargement.

Proche de l'Agent Config d'ADK (agent_class, name, model, description, instruction, tools),
avec trois champs de FORGE CODE : skills (procédures chargées à la demande), scope (fichiers
que l'agent peut modifier) et acceptance (commande de test qui juge son travail). La fiche est
lue avec yaml.safe_load ; outils et skills sont des noms pris dans un catalogue : rien n'y
désigne du code Python à importer, contrairement au chargeur YAML d'ADK (outils et callbacks
par chemin de module).
"""

import re
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..tools._workspace import workspace

# Outils qu'une fiche peut demander : tous sont aussi des outils de l'Atelier.
# Execute n'y est pas : l'acceptance passe par run_tests, et une commande libre dans le banc
# d'essai, en mode automatique, échapperait à toute confirmation.
OUTILS_AUTORISES = ("read_file", "search", "outline", "list_files", "git_lecture",
                    "edit_file", "write_file", "run_tests")
Outil = Literal["read_file", "search", "outline", "list_files", "git_lecture",
                "edit_file", "write_file", "run_tests"]

# Noms déjà pris par les agents et outils de FORGE CODE.
NOMS_RESERVES = {"atelier", "explorateur", "diagnostiqueur", "migrateur", "redacteur_tests",
                 "migrer_partout", "evaluateur_agent", "forgeron_agent", "banc_essai_agent",
                 "verificateur_agent", "user", *OUTILS_AUTORISES}

def dossiers_de_skills() -> list[Path]:
    """Catalogue des skills : celles de FORGE CODE (app/skills), puis celles forgées pour le
    dépôt (.forge/skills), versionnées avec son code. Une skill = un dossier avec SKILL.md."""
    return [Path(__file__).parent.parent / "skills", workspace() / ".forge" / "skills"]


def skills_disponibles() -> dict[str, Path]:
    """Nom de chaque skill du catalogue -> son dossier (une skill du dépôt l'emporte)."""
    return {d.name: d for racine in dossiers_de_skills() if racine.is_dir()
            for d in sorted(racine.iterdir()) if (d / "SKILL.md").is_file()}


_ACCEPTANCE = re.compile(r"(python -m )?pytest( [\w./:\\\[\]=-]+)*")


class Fiche(BaseModel):
    # Un champ inconnu (ex. callbacks, code) est refusé, pas ignoré.
    model_config = ConfigDict(extra="forbid")

    agent_class: Literal["LlmAgent"] = "LlmAgent"
    name: str = Field(description="Identifiant snake_case du sous-agent, unique dans le registre")
    model: str = Field(default="gemini-2.5-flash", description="Modèle Gemini du sous-agent")
    description: str = Field(min_length=1, max_length=500,
                             description="QUAND l'appeler et QUOI il fait : lue par l'Atelier")
    instruction: str = Field(min_length=1, max_length=8000, description="Prompt du sous-agent")
    tools: list[Outil] = Field(min_length=1, description="Outils autorisés, par nom")
    skills: list[str] = Field(default_factory=list,
                              description="Skills du catalogue (app/skills, .forge/skills) qu'il peut charger")
    scope: list[str] = Field(min_length=1, description="Motifs des fichiers qu'il peut modifier, ex. src/billing/**")
    acceptance: str = Field(description="Commande pytest qui juge le résultat, ex. pytest tests/billing")

    @field_validator("name")
    @classmethod
    def nom_valide(cls, name: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,49}", name):
            raise ValueError(f"« {name} » : le nom est en snake_case (minuscules, chiffres, _), 3 à 50 caractères.")
        if name in NOMS_RESERVES:
            raise ValueError(f"« {name} » est déjà le nom d'un agent ou d'un outil de FORGE CODE.")
        return name

    @field_validator("model")
    @classmethod
    def modele_gemini(cls, model: str) -> str:
        if not re.fullmatch(r"gemini-[\w.-]+", model):
            raise ValueError(f"« {model} » n'est pas un modèle Gemini (ex. gemini-2.5-flash).")
        return model

    @field_validator("tools")
    @classmethod
    def outils_uniques(cls, tools: list[str]) -> list[str]:
        return list(dict.fromkeys(tools))

    @field_validator("skills")
    @classmethod
    def skills_du_catalogue(cls, skills: list[str]) -> list[str]:
        disponibles = skills_disponibles()
        inconnues = [s for s in skills if s not in disponibles]
        if inconnues:
            raise ValueError(f"Skills inconnues : {', '.join(inconnues)}. Skills disponibles : "
                             f"{', '.join(disponibles) or 'aucune'}.")
        return list(dict.fromkeys(skills))

    @field_validator("scope")
    @classmethod
    def perimetre_dans_le_depot(cls, scope: list[str]) -> list[str]:
        motifs = []
        for motif in scope:
            m = motif.strip().replace("\\", "/").removeprefix("./")
            chemin = PurePosixPath(m)
            if not m or chemin.is_absolute() or re.match(r"[A-Za-z]:", m) or ".." in chemin.parts:
                raise ValueError(f"« {motif} » : le périmètre est un motif relatif au dépôt, sans « .. ».")
            if m in ("*", "**", "**/*") or chemin.parts[0] in (".git", ".forge"):
                raise ValueError(f"« {motif} » : le périmètre doit viser des fichiers précis, pas tout le dépôt.")
            motifs.append(m)
        return motifs

    @field_validator("acceptance")
    @classmethod
    def commande_pytest(cls, acceptance: str) -> str:
        commande = " ".join(acceptance.split())
        if not _ACCEPTANCE.fullmatch(commande):
            raise ValueError(f"« {acceptance} » : l'acceptance est une commande pytest seule "
                             "(ex. pytest tests/billing), sans chaînage ni redirection.")
        return commande


def lire_fiche(chemin: Path) -> Fiche:
    """Lit et valide une fiche YAML (ValidationError si elle n'est pas conforme)."""
    return Fiche.model_validate(yaml.safe_load(Path(chemin).read_text(encoding="utf-8")) or {})


def ecrire_fiche(fiche: Fiche, chemin: Path) -> None:
    """Écrit la fiche en YAML lisible, versionnable avec le code."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(yaml.safe_dump(fiche.model_dump(), allow_unicode=True, sort_keys=False),
                      encoding="utf-8")
