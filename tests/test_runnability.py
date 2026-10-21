"""Vérifie que l'application, l'agent racine, ses outils et ses sous-agents se chargent."""

import asyncio
import json
import os
import subprocess
import sys


def test_root_agent_loads():
    from app.agent import root_agent

    assert root_agent.name == "atelier"
    tools = asyncio.run(root_agent.canonical_tools())
    assert {t.name for t in tools} == {
        "ReadFile",
        "WriteFile",
        "Execute",
        "search",
        "outline",
        "edit_file",
        "run_tests",
        "outil_inconnu",
        "explorateur",
        "diagnostiqueur",
        "migrateur",
        "migrer_partout",
        "redacteur_tests",
        "load_skill",
    }


def test_modele_retente_en_cas_de_quota():
    from app.agent import root_agent

    assert root_agent.model.retry_options.attempts == 5


def test_app_avec_reflect_and_retry():
    from app.agent import app, root_agent

    assert app.root_agent is root_agent
    assert [type(p).__name__ for p in app.plugins] == ["ReflectAndRetryToolPlugin", "RedirectionOutilsInconnus",
                                                       "IndicesCibles", "VerificationApresEcriture"]


def test_sans_specialistes_configurations_a_et_b():
    # Réglage lu au chargement de l'agent : vérifié dans un processus neuf.
    code = ("import asyncio, json; from app.agent import root_agent; "
            "print(json.dumps([sorted(t.name for t in asyncio.run(root_agent.canonical_tools())), "
            "'spécialistes' in root_agent.instruction]))")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "FORGE_SPECIALISTES": "off", "PYTHONIOENCODING": "utf-8"})
    outils, parle_des_specialistes = json.loads(proc.stdout.strip().splitlines()[-1])
    assert outils == ["Execute", "ReadFile", "WriteFile", "edit_file", "outil_inconnu", "outline", "run_tests",
                      "search"]
    assert not parle_des_specialistes


def test_chaque_specialiste_dit_quand_l_appeler():
    # L'Atelier choisit un outil en lisant sa description : elle dit quand, quoi et quoi donner.
    from app.agent import root_agent

    outils = {t.name: t for t in asyncio.run(root_agent.canonical_tools())}
    for nom in ("explorateur", "diagnostiqueur", "migrateur", "migrer_partout", "redacteur_tests"):
        description = outils[nom]._get_declaration().description
        assert all(mot in description for mot in ("QUAND :", "QUOI :", "DONNE-LUI :")), nom


def test_writefile_ne_renvoie_plus_vers_editfile():
    from app.agent import root_agent

    writefile = next(t for t in asyncio.run(root_agent.canonical_tools()) if t.name == "WriteFile")
    description = writefile._get_declaration().description
    assert "EditFile" not in description and "edit_file" in description

