"""Tests de l'explorateur : lecture seule, references, list_files, git_lecture."""

import asyncio
import subprocess
import textwrap

import pytest
from pydantic import ValidationError

from app.context.references import references
from app.sub_agents.explorateur import explorateur
from app.sub_agents.explorateur.schema import RapportExploration
from app.tools import git_lecture, list_files


def test_explorateur_en_lecture_seule():
    outils = {t.name for t in asyncio.run(explorateur.canonical_tools())}
    assert outils == {"search", "references", "list_files", "outline", "git_lecture", "ReadFile"}


def test_rapport_valide():
    rapport = RapportExploration.model_validate_json(
        '{"statut": "trouve", "fichiers": [{"chemin": "src/a.py", "lignes": "1-5", "role": "calcule"}],'
        ' "explication": "...", "confiance": "verifie"}')
    assert rapport.fichiers[0].chemin == "src/a.py" and rapport.a_surveiller == []
    with pytest.raises(ValidationError):   # statut inconnu : refusé
        RapportExploration.model_validate_json('{"statut": "peut-etre", "explication": "", "confiance": "verifie"}')
    assert explorateur.output_schema is RapportExploration


@pytest.fixture
def depot(tmp_path, monkeypatch):
    paquet = tmp_path / "src" / "boutique"
    paquet.mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    (paquet / "remises.py").write_text(textwrap.dedent("""\
        def appliquer_remise(montant, taux=0.0):
            return montant * (1 - taux)
    """), encoding="utf-8")
    (paquet / "panier.py").write_text(textwrap.dedent("""\
        from .remises import appliquer_remise


        def total(prix):
            return appliquer_remise(sum(prix))
    """), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_panier.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (tmp_path / ".env").write_text("CLE=secret\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


# ------------------------------------------------------------------ references

def test_references_definition_utilisations_et_imports(depot):
    resultat = references("appliquer_remise")
    assert resultat["definitions"] == ["src/boutique/remises.py:1-2  def appliquer_remise(montant, taux=0.0)"]
    assert resultat["importe_par"] == ["src/boutique/panier.py"]
    utilisations = " ".join(resultat["utilisations"])
    assert "src/boutique/panier.py:1" in utilisations                # l'import
    assert "src/boutique/panier.py:5 (dans total)" in utilisations   # l'appel
    assert "remises.py:1" not in utilisations                        # la définition n'est pas une utilisation


def test_references_symbole_inconnu(depot):
    resultat = references("inexistant")
    assert resultat == {"definitions": [], "utilisations": [], "utilisations_tronquees": False,
                        "importe_par": []}


# ------------------------------------------------------------------ list_files

def test_list_files_par_motif(depot):
    assert list_files("**/test_*.py")["fichiers"] == ["tests/test_panier.py"]
    assert list_files("src/**/*.py")["fichiers"] == [
        "src/boutique/__init__.py", "src/boutique/panier.py", "src/boutique/remises.py"]


def test_list_files_ignore_les_secrets_et_limite(depot):
    resultat = list_files("**/*", max_results=2)
    assert ".env" not in resultat["fichiers"]
    assert resultat["truncated"] is True and len(resultat["fichiers"]) == 2


def test_list_files_refuse_de_sortir_du_depot(depot):
    for motif in ("../*", "/etc/*", "C:/*"):
        with pytest.raises(ValueError):
            list_files(motif)


# ----------------------------------------------------------------- git_lecture

@pytest.fixture
def depot_git(depot):
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q"], cwd=depot, check=True)
    subprocess.run([*git, "add", "-A"], cwd=depot, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "ajoute les remises"], cwd=depot, check=True)
    return depot


def test_git_lecture_commandes_permises(depot_git):
    assert "ajoute les remises" in git_lecture("log --oneline")["sortie"]
    assert "appliquer_remise" in git_lecture("git grep -n appliquer_remise")["sortie"]
    blame = git_lecture("blame -L 1,1 src/boutique/remises.py")
    assert blame["code"] == 0 and "def appliquer_remise" in blame["sortie"]


@pytest.mark.parametrize("commande", [
    "commit -m x",                         # écriture
    "push",                                # réseau
    "checkout -- src",                     # écriture
    "diff --output=fichier.txt",           # écrit un fichier
    "grep -O notepad x",                   # lance un programme
    "",
])
def test_git_lecture_refuse_le_reste(depot_git, commande):
    with pytest.raises(ValueError):
        git_lecture(commande)


def test_git_lecture_sans_enchainement_possible(depot_git):
    # Pas de shell : « ; » et « && » ne sont que des arguments, rien n'est exécuté en plus.
    resultat = git_lecture("log --oneline ; echo PIRATE")
    assert "PIRATE" not in resultat["sortie"]
