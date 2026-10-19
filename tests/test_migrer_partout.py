"""Tests de migrer_partout : inventaire, un migrateur par fichier, vérification finale.

Le migrateur est remplacé par un faux qui fait le remplacement en Python : pas d'appel au modèle.
"""

import asyncio
import re

import pytest
from google.adk.tools.function_tool import FunctionTool

from app.agent import atelier
from app.permissions import decide
from app.orchestration import migrer_partout as mp
from app.orchestration.migrer_partout import demande_au_migrateur, inventaire, migrer_partout, motif


@pytest.fixture
def depot(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text("def mark_internal(f):\n    return f\n", encoding="utf-8")
    (tmp_path / "src" / "a.py").write_text(
        "from .utils import internalcode\n\n@internalcode\ndef f():\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text(
        '__all__ = ["internalcode"]\nx = is_internalcode_like = 1\n', encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("# internalcode\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


def faux_migrateur(depot, demandes, laisser=0):
    """Remplace l'ancien code dans le fichier confié ; en laisse `laisser` occurrences."""
    async def lancer(demande, tool_context):
        demandes.append(demande)
        fichier = re.search(r"Fichier confié : (\S+)", demande).group(1)
        ancien = re.search(r"Ancien code : (\S+)", demande).group(1)
        nouveau = re.search(r"Nouveau code : (\S+)", demande).group(1)
        chemin = depot / fichier
        texte = chemin.read_text(encoding="utf-8")
        nombre = len(re.findall(motif(ancien), texte))
        if nombre > laisser:   # count=0 voudrait dire « tout remplacer »
            texte = re.sub(motif(ancien), nouveau, texte, count=nombre - laisser)
        chemin.write_text(texte, encoding="utf-8")
        return {"statut": "migre" if not laisser else "partiel", "fichier": fichier,
                "modifications": [f"occurrence {i}" for i in range(nombre - laisser)],
                "occurrences_restantes": laisser, "incertitudes": []}
    return lancer


def migrer(**kwargs):
    return asyncio.run(migrer_partout(tool_context=None, **kwargs))


def test_motif_en_mot_entier():
    assert re.search(motif("internalcode"), "@internalcode")
    assert not re.search(motif("internalcode"), "is_internalcode_like")
    assert re.search(motif("jinja2.utils."), "from jinja2.utils.x")


def test_inventaire_par_fichier_et_exclusions(depot):
    tout = inventaire("internalcode")
    assert set(tout) == {"src/a.py", "src/b.py", "tests/test_a.py"}
    assert len(tout["src/a.py"]) == 2
    assert set(inventaire("internalcode", exclure=["tests/", "src/b.py"])) == {"src/a.py"}
    assert set(inventaire("internalcode", exclure=["src/*.py"])) == {"tests/test_a.py"}


def test_migre_chaque_fichier_une_fois(depot, monkeypatch):
    demandes = []
    monkeypatch.setattr(mp, "lancer_migrateur", faux_migrateur(depot, demandes))
    resultat = migrer(ancien="internalcode", nouveau="mark_internal",
                      regle="renomme le décorateur", exclure=["tests"])
    assert resultat["statut"] == "migre"
    assert resultat["occurrences_restantes"] == []
    assert resultat["fichiers"] == {"src/a.py": {"statut": "migre", "modifications": 2},
                                    "src/b.py": {"statut": "migre", "modifications": 1}}
    assert len(demandes) == 2
    # Les tests exclus ne sont pas touchés ; le faux ami non plus.
    assert "internalcode" in (depot / "tests" / "test_a.py").read_text(encoding="utf-8")
    assert "is_internalcode_like" in (depot / "src" / "b.py").read_text(encoding="utf-8")


def test_demande_cite_le_fichier_et_ses_occurrences(depot):
    occurrences = inventaire("internalcode")["src/a.py"]
    demande = demande_au_migrateur("src/a.py", "internalcode", "mark_internal", "renomme", "", occurrences)
    assert "Fichier confié : src/a.py" in demande
    assert all(o in demande for o in occurrences)


def test_partiel_quand_il_reste_des_occurrences(depot, monkeypatch):
    monkeypatch.setattr(mp, "lancer_migrateur", faux_migrateur(depot, [], laisser=1))
    resultat = migrer(ancien="internalcode", nouveau="mark_internal", regle="renomme", exclure=["tests"])
    assert resultat["statut"] == "partiel"
    assert len(resultat["occurrences_restantes"]) == 2
    assert "edit_file" in resultat["ensuite"]


def test_un_fichier_en_erreur_n_arrete_pas_les_autres(depot, monkeypatch):
    vrai = faux_migrateur(depot, [])

    async def lancer(demande, tool_context):
        if "src/a.py" in demande:
            raise RuntimeError("modèle indisponible")
        return await vrai(demande, tool_context)

    monkeypatch.setattr(mp, "lancer_migrateur", lancer)
    resultat = migrer(ancien="internalcode", nouveau="mark_internal", regle="renomme", exclure=["tests"])
    assert resultat["fichiers"]["src/a.py"]["statut"] == "erreur"
    assert "modèle indisponible" in resultat["fichiers"]["src/a.py"]["erreur"]
    assert resultat["fichiers"]["src/b.py"]["statut"] == "migre"
    assert resultat["statut"] == "partiel"


def test_rien_a_faire(depot, monkeypatch):
    monkeypatch.setattr(mp, "lancer_migrateur", faux_migrateur(depot, []))
    resultat = migrer(ancien="introuvable", nouveau="x", regle="renomme")
    assert resultat["statut"] == "rien_a_faire"


def test_declaration_pour_le_modele():
    declaration = FunctionTool(migrer_partout)._get_declaration()
    schema = declaration.parameters_json_schema   # tool_context n'est pas montré au modèle
    assert set(schema["properties"]) == {"ancien", "nouveau", "regle", "exemple", "path", "glob", "exclure"}
    assert set(schema["required"]) == {"ancien", "nouveau", "regle"}


def test_branche_dans_l_atelier_et_autorise():
    noms = {t.name for t in asyncio.run(atelier.canonical_tools())}
    assert "migrer_partout" in noms
    assert decide("migrer_partout", {}, mode="ask")[0] == "allow"
