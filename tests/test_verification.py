"""Tests de la frontière des preuves et de la vérification juste après une écriture."""

import asyncio
from types import SimpleNamespace

import pytest

from app.prompt import FRONTIERE_DES_PREUVES, atelier_prompt
from app.plugins.verification import VerificationApresEcriture, verifier_import


# -------------------------------------------------------- frontière des preuves

def test_frontiere_des_preuves_pour_tous_les_agents():
    from app.sub_agents.diagnostiqueur import diagnostiqueur
    from app.sub_agents.explorateur import explorateur
    from app.sub_agents.migrateur import migrateur
    from app.sub_agents.redacteur_tests import redacteur_tests

    assert FRONTIERE_DES_PREUVES in atelier_prompt(specialistes=True)
    assert FRONTIERE_DES_PREUVES in atelier_prompt(specialistes=False)   # configurations A et B aussi
    for agent in (explorateur, diagnostiqueur, migrateur, redacteur_tests):
        assert FRONTIERE_DES_PREUVES in agent.instruction, agent.name


# ------------------------------------------------------ vérification d'import

@pytest.fixture
def depot(tmp_path, monkeypatch):
    paquet = tmp_path / "src" / "boutique"
    paquet.mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    (paquet / "remises.py").write_text("def remise(x):\n    return x\n", encoding="utf-8")
    (paquet / "panier.py").write_text("from .remises import remise\n\nTOTAL = remise(1)\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("raise RuntimeError\n", encoding="utf-8")
    (tmp_path / "script.py").write_text("raise RuntimeError\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


def test_module_qui_s_importe_rien_a_signaler(depot):
    assert verifier_import("src/boutique/panier.py") == ""


def test_nom_indefini_dans_le_fichier_modifie_signale(depot):
    (depot / "src/boutique/panier.py").write_text("TOTAL = remise_inconnue(1)\n", encoding="utf-8")
    probleme = verifier_import("src/boutique/panier.py")
    assert "ne s'importe plus" in probleme and "NameError" in probleme


def test_erreur_venant_d_un_autre_fichier_pas_signalee(depot):
    # Le dépôt était déjà cassé ailleurs : ce n'est pas la modification de panier.py la cause.
    (depot / "src/boutique/remises.py").write_text("raise ImportError('cassé ailleurs')\n", encoding="utf-8")
    assert verifier_import("src/boutique/panier.py") == ""


@pytest.mark.parametrize("chemin", ["tests/test_x.py", "script.py", "README.md", "../ailleurs.py"])
def test_fichiers_non_verifies(depot, chemin):
    assert verifier_import(chemin) == ""


def test_erreur_deja_presente_avant_la_modification_pas_signalee(depot):
    # Cas de jinja-011 : le fichier était déjà cassé avant (injection) ; la modification
    # n'y est pour rien et ne doit pas déclencher d'alerte.
    panier = depot / "src/boutique/panier.py"
    panier.write_text("TOTAL = remise_inconnue(1)\n", encoding="utf-8")
    from app.plugins.verification import erreur_import
    avant = erreur_import("src/boutique/panier.py")
    panier.write_text("# commentaire\nTOTAL = remise_inconnue(1)\n", encoding="utf-8")   # édition sans effet
    assert verifier_import("src/boutique/panier.py", erreur_avant=avant) == ""


def modifier_avec_le_plugin(outil, args, nouveau_contenu, depot, resultat):
    """Le déroulé réel : vérification avant l'outil, l'outil écrit, vérification après."""
    plugin, outil = VerificationApresEcriture(), SimpleNamespace(name=outil)
    asyncio.run(plugin.before_tool_callback(tool=outil, tool_args=args, tool_context=None))
    if nouveau_contenu is not None:
        (depot / args["path"]).write_text(nouveau_contenu, encoding="utf-8")
    return asyncio.run(plugin.after_tool_callback(tool=outil, tool_args=args, tool_context=None, result=resultat))


def test_plugin_signale_une_erreur_nouvelle(depot):
    sortie = modifier_avec_le_plugin("edit_file", {"path": "src/boutique/panier.py"},
                                     "TOTAL = remise_inconnue(1)\n", depot, {"status": "ok", "diff": "..."})
    assert sortie["diff"] == "..." and "NameError" in sortie["verification"]


def test_plugin_silencieux_si_tout_va_bien(depot):
    sortie = modifier_avec_le_plugin("edit_file", {"path": "src/boutique/panier.py"},
                                     "from .remises import remise\n\nTOTAL = remise(2)\n", depot, {"status": "ok"})
    assert sortie is None


def test_plugin_ne_touche_pas_aux_autres_outils_ni_aux_echecs(depot):
    assert modifier_avec_le_plugin("search", {"path": "src/boutique/panier.py"}, None, depot, {"matches": []}) is None
    assert modifier_avec_le_plugin("edit_file", {"path": "src/boutique/panier.py"}, None, depot,
                                   {"error": "introuvable"}) is None
