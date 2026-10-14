"""Tests de l'indexation, de la sélection et de l'assemblage du contexte compilé."""

import textwrap

import pytest
from google.adk.models import LlmRequest
from google.genai import types

from app.context import assemblage
from app.context.assemblage import contexte_compile, extraire_contraintes
from app.context.compiler import compiler
from app.context.indexer import indexer
from app.context.selection import morceaux, mots_de, selectionner


@pytest.fixture
def depot(tmp_path, monkeypatch):
    """Un petit paquet : panier.py importe remises.py ; un test associé."""
    paquet = tmp_path / "src" / "boutique"
    paquet.mkdir(parents=True)
    (paquet / "__init__.py").write_text("", encoding="utf-8")
    (paquet / "remises.py").write_text(textwrap.dedent('''\
        def appliquer_remise(montant: float, taux: float = 0.0) -> float:
            """Applique une remise."""
            return montant * (1 - taux)
    '''), encoding="utf-8")
    (paquet / "panier.py").write_text(textwrap.dedent('''\
        from .remises import appliquer_remise


        class Panier:
            def calculer_total(self, prix, quantites):
                """Total du panier."""
                return sum(p * q for p, q in zip(prix, quantites))
    '''), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_panier.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    return tmp_path


def test_index_symboles_signatures_et_imports(depot):
    index = indexer(depot)
    panier = index.fichiers["src/boutique/panier.py"]
    assert panier.module == "boutique.panier"
    assert [s.nom for s in panier.symboles] == ["Panier", "calculer_total"]
    assert panier.imports == {"src/boutique/remises.py"}
    remise = index.fichiers["src/boutique/remises.py"].symboles[0]
    assert remise.signature == "def appliquer_remise(montant, taux=0.0)"   # sans annotations
    assert remise.doc == "Applique une remise."
    assert index.importe_par("src/boutique/remises.py") == ["src/boutique/panier.py"]


def test_index_mis_a_jour_quand_le_fichier_change(depot):
    indexer(depot)
    (depot / "src/boutique/remises.py").write_text("def nouvelle():\n    pass\n", encoding="utf-8")
    noms = [s.nom for s in indexer(depot).fichiers["src/boutique/remises.py"].symboles]
    assert noms == ["nouvelle"]


def test_mots_et_morceaux():
    assert mots_de("Les éléments de calculer_total") == ["calculer_total"]   # « éléments » ignoré
    assert morceaux("visit_EvalContextModifier") == ["visit", "eval", "context", "modifier"]


def test_selection_du_fichier_principal_voisins_et_tests(depot):
    selection = selectionner(indexer(depot), "Le calcul de calculer_total est faux.", [])
    assert selection.principal == "src/boutique/panier.py"
    assert [s.nom for _, s in selection.symboles] == ["calculer_total"]
    assert selection.voisins == ["src/boutique/remises.py"]
    assert selection.tests == ["tests/test_panier.py"]


def test_selection_par_morceau_de_nom(depot):
    selection = selectionner(indexer(depot), "La remise est mal appliquée.", [])
    assert selection.principal == "src/boutique/remises.py"


def test_fichier_modifie_pendant_la_session_prioritaire(depot):
    selection = selectionner(indexer(depot), "Continue.", ["src/boutique/remises.py"])
    assert selection.principal == "src/boutique/remises.py"


def test_contraintes_extraites():
    consigne = "Corrige le bug. Ne modifie que panier.py et ne touche pas aux tests. Merci."
    assert extraire_contraintes(consigne) == ["Ne modifie que panier.py et ne touche pas aux tests."]


def test_bloc_ordonne_contraintes_code_tests_carte_voisins(depot):
    bloc = contexte_compile(depot, "Corrige calculer_total sans toucher aux tests.", [])
    positions = [bloc.index(t) for t in ("## Contraintes", "## Code à examiner", "## Tests associés",
                                         "## Carte de src/boutique/panier.py", "## Fichier lié")]
    assert positions == sorted(positions)
    assert "return sum(p * q for p, q in zip(prix, quantites))" in bloc   # code du symbole visé


def test_bloc_vide_sans_rien_a_selectionner(depot):
    assert contexte_compile(depot, "Bonjour.", []) == ""


def test_agents_md_en_tete_du_bloc(depot):
    (depot / "AGENTS.md").write_text("Lance les tests avec pytest -q.", encoding="utf-8")
    bloc = contexte_compile(depot, "Corrige calculer_total sans toucher aux tests.", [])
    assert bloc.index("## Instructions du projet (AGENTS.md)") < bloc.index("## Contraintes")
    assert "Lance les tests avec pytest -q." in bloc
    assert "Instructions du projet" in contexte_compile(depot, "Bonjour.", [])   # même sans sélection


def test_budget_respecte(depot, monkeypatch):
    monkeypatch.setattr(assemblage, "BUDGET", 400)
    bloc = contexte_compile(depot, "Corrige calculer_total sans toucher aux tests.", [])
    assert len(bloc) <= 400 + len("\n… (coupé : budget atteint)")


def test_compiler_place_le_bloc_en_tete(depot, monkeypatch):
    monkeypatch.setenv("FORGE_CONTEXT", "on")
    requete = LlmRequest(contents=[types.Content(role="user", parts=[types.Part(text="Corrige calculer_total.")])])
    compiler(None, requete)
    assert "Contexte compilé par FORGE CODE" in str(requete.config.system_instruction)
