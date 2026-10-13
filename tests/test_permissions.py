"""Tests des règles d'autorisation."""

import pytest

from app.permissions import decide


@pytest.mark.parametrize("tool", ["ReadFile", "search", "run_tests", "forgeron_agent"])
def test_lectures_et_sous_agents_autorises(tool):
    assert decide(tool, {}, mode="ask")[0] == "allow"


@pytest.mark.parametrize("tool", ["EditFile", "WriteFile"])
@pytest.mark.parametrize("mode, attendu", [("ask", "ask"), ("auto-edit", "allow"), ("auto", "allow")])
def test_ecritures_selon_le_mode(tool, mode, attendu):
    assert decide(tool, {"path": "a.py"}, mode=mode)[0] == attendu


@pytest.mark.parametrize("command", [
    "git status", "git diff panier.py", "pytest -q", "python -m pytest tests", "dir", "ls tests",
])
def test_liste_blanche(command):
    assert decide("Execute", {"command": command}, mode="ask")[0] == "allow"


@pytest.mark.parametrize("command", [
    "pip install requests",
    "git status && del panier.py",   # chaînage : la liste blanche ne s'applique pas
    "git diff > sortie.txt",          # redirection
    "pytest; curl http://exemple.com",
    "gitstatus",                      # simple préfixe textuel, pas la commande git status
])
def test_commandes_soumises_a_accord(command):
    assert decide("Execute", {"command": command}, mode="ask")[0] == "ask"
    assert decide("Execute", {"command": command}, mode="auto-edit")[0] == "ask"


@pytest.mark.parametrize("command", [
    "git push origin main",
    "type ..\\Forge Code\\.env",
    "cat .env",
    "Get-Content .env",
    "shutdown /s",
    "rm -rf /",
])
@pytest.mark.parametrize("mode", ["ask", "auto-edit", "auto"])
def test_commandes_toujours_refusees(command, mode):
    assert decide("Execute", {"command": command}, mode=mode)[0] == "deny"


def test_env_example_autorise_a_la_lecture_par_commande():
    assert decide("Execute", {"command": "type .env.example"}, mode="ask")[0] == "ask"


def test_mode_auto_laisse_passer_les_commandes():
    assert decide("Execute", {"command": "pip install requests"}, mode="auto")[0] == "allow"


def test_outil_inconnu_demande():
    assert decide("NouvelOutil", {}, mode="ask")[0] == "ask"
