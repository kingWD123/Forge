"""Tests de l'outil edit_file."""

import pytest

from app.tools import edit_file

PANIER = (
    "def total(prix, quantites, remise=0.0):\n"
    "    brut = sum(p * q for p, q in zip(prix, quantites))\n"
    "    return round(brut * (1 + remise), 2)\n"
)


@pytest.fixture
def depot(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    (tmp_path / "panier.py").write_bytes(PANIER.encode())
    return tmp_path


def lire(depot, nom="panier.py"):
    return (depot / nom).read_bytes().decode()


def test_remplacement_simple(depot):
    result = edit_file("panier.py", "(1 + remise)", "(1 - remise)")
    assert result["status"] == "ok"
    assert "(1 - remise)" in lire(depot)


def test_indentation_pas_doublee(depot):
    # Le cas observé avec Gemini : old sans indentation, new avec.
    edit_file("panier.py", "return round(brut * (1 + remise), 2)",
              "    return round(brut * (1 - remise), 2)")
    assert lire(depot).splitlines()[2] == "    return round(brut * (1 - remise), 2)"


def test_indentation_relative_conservee(depot):
    # old et new sans indentation : on garde celle du fichier.
    edit_file("panier.py", "return round(brut * (1 + remise), 2)",
              "return round(brut * (1 - remise), 2)")
    assert lire(depot).splitlines()[2] == "    return round(brut * (1 - remise), 2)"


def test_fins_de_ligne_windows_conservees(depot):
    (depot / "panier.py").write_bytes(PANIER.replace("\n", "\r\n").encode())
    edit_file("panier.py", "    return round(brut * (1 + remise), 2)\n",
              "    # remise soustraite\n    return round(brut * (1 - remise), 2)\n")
    contenu = lire(depot)
    assert "# remise soustraite" in contenu
    assert contenu.count("\n") == contenu.count("\r\n")  # aucune fin de ligne Unix isolée


def test_syntaxe_python_cassee_refusee(depot):
    with pytest.raises(ValueError, match="syntaxe Python"):
        edit_file("panier.py", "    return round(brut * (1 + remise), 2)",
                  "        return round(brut * (1 - remise), 2)")
    assert lire(depot) == PANIER  # rien n'a été écrit


def test_bloc_introuvable(depot):
    with pytest.raises(ValueError, match="introuvable"):
        edit_file("panier.py", "n'existe pas", "x")


def test_bloc_en_double(depot):
    (depot / "a.txt").write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError, match="2 fois"):
        edit_file("a.txt", "x = 1", "x = 2")


def test_fichier_absent(depot):
    with pytest.raises(ValueError, match="WriteFile"):
        edit_file("absent.py", "a", "b")


def test_secret_refuse(depot):
    (depot / ".env").write_text("CLE=1\n")
    with pytest.raises(ValueError, match="secrets"):
        edit_file(".env", "CLE=1", "CLE=2")


def test_hors_depot_refuse(depot):
    with pytest.raises(ValueError, match="hors du dépôt"):
        edit_file("../ailleurs.py", "a", "b")
