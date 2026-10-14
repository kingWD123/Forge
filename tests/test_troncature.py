"""Tests de la coupe des sorties d'outils trop longues."""

from types import SimpleNamespace

from app.context.troncature import LIMITE, couper_debut_et_fin, couper_lecture, tronquer_sorties


def outil(nom):
    return SimpleNamespace(name=nom)


def test_sortie_courte_inchangee():
    assert couper_debut_et_fin("ok") == "ok"
    assert tronquer_sorties(outil("Execute"), {}, None, {"stdout": "ok", "stderr": ""}) is None


def test_commande_garde_le_debut_et_la_fin():
    lignes = [f"ligne {n}" for n in range(5000)]
    lignes[-1] = "AssertionError: la vraie cause"   # la cause est en bas
    texte = couper_debut_et_fin("\n".join(lignes))
    assert texte.startswith("ligne 0")
    assert texte.endswith("AssertionError: la vraie cause")
    assert "lignes retirées au milieu" in texte
    assert len(texte) < LIMITE + 100


def test_execute_coupe_stdout_et_stderr():
    long = "x\n" * 10_000
    reponse = tronquer_sorties(outil("Execute"), {}, None, {"stdout": long, "stderr": long, "exit_code": 1})
    assert "lignes retirées au milieu" in reponse["stdout"]
    assert "lignes retirées au milieu" in reponse["stderr"]
    assert reponse["exit_code"] == 1


def test_lecture_indique_ou_reprendre():
    contenu = "\n".join(f"{n:>6}\tcode de la ligne {n}" for n in range(1, 2000))
    texte = couper_lecture(contenu)
    derniere = texte.rsplit("\n", 2)[-2]
    numero = int(derniere.split("\t")[0])
    assert f"start_line={numero + 1}" in texte


def test_autres_outils_non_touches():
    assert tronquer_sorties(outil("search"), {}, None, {"matches": ["x" * 20_000]}) is None
