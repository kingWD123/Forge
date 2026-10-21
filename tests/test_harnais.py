"""Tests du harnais de l'Atelier selon les formes de Harness² : skills chargées à la demande,
plugin d'indices ciblés, texte permanent réduit."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from google.adk.events import Event
from google.adk.skills import load_skills_from_dir
from google.genai import types

from app import prompt
from app.indices import SEUIL_ECHECS, indice_pour

SKILLS = Path(__file__).resolve().parent.parent / "app" / "skills"


# --------------------------------------------------------------------- skills

def test_skills_valides():
    skills = {s.name: s for s in load_skills_from_dir(SKILLS)}
    assert set(skills) == {"migration", "ecriture-tests"}
    assert "migrer_partout" in skills["migration"].instructions
    assert "redacteur_tests" in skills["ecriture-tests"].instructions


def test_chaque_skill_a_sa_ligne_de_declenchement():
    # Règle n°1 de Harness² : une skill non nommée dans le texte permanent n'est jamais ouverte.
    for skill in load_skills_from_dir(SKILLS):
        assert f"`{skill.name}`" in prompt.atelier_prompt(specialistes=True)


def test_skills_chargees_a_la_demande():
    from app.agent import root_agent

    outils = {t.name for t in asyncio.run(root_agent.canonical_tools())}
    assert "load_skill" in outils
    assert not outils & {"load_skill_resource", "run_skill_script"}   # nos skills n'ont ni fichier ni script
    # La procédure de migration n'est plus dans le texte permanent.
    assert "exclure" not in root_agent.instruction


# ------------------------------------------------------------ texte permanent

def test_texte_permanent_court():
    # Chaque caractère du prompt est payé à chaque appel au modèle.
    assert len(prompt.atelier_prompt(specialistes=True)) < 2_500


# -------------------------------------------------------------------- indices

def contexte(consigne, outils, deja_appeles=()):
    evenements = [Event(author="user", content=types.Content(role="user", parts=[types.Part(text=consigne)]))]
    for nom in deja_appeles:
        evenements.append(Event(author="atelier", content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name=nom, args={}))])))
    agent = SimpleNamespace(tools=[SimpleNamespace(name=nom) for nom in outils])
    return SimpleNamespace(session=SimpleNamespace(events=evenements),
                           _invocation_context=SimpleNamespace(agent=agent), user_content=None)


def sortie_de_tests(n):
    return {"status": "failed", "counts": {"failed": n, "passed": 10}}


def test_indice_diagnostiqueur_au_dela_du_seuil():
    ctx = contexte("Corrige le bug.", ["run_tests", "diagnostiqueur"])
    assert "diagnostiqueur" in indice_pour("run_tests", sortie_de_tests(SEUIL_ECHECS + 1), ctx)
    assert indice_pour("run_tests", sortie_de_tests(SEUIL_ECHECS), ctx) == ""


def test_pas_d_indice_si_deja_appele_ou_indisponible():
    deja = contexte("Corrige.", ["run_tests", "diagnostiqueur"], deja_appeles=["diagnostiqueur"])
    assert indice_pour("run_tests", sortie_de_tests(90), deja) == ""
    sans_specialistes = contexte("Corrige.", ["run_tests"])   # configurations A et B
    assert indice_pour("run_tests", sortie_de_tests(90), sans_specialistes) == ""


def recherche(*fichiers):
    return {"matches": [f"{f}:1: internalcode" for f in fichiers], "total": len(fichiers)}


def test_indice_migration():
    ctx = contexte("Le décorateur a été renommé : migre tout le code.", ["search", "migrer_partout"])
    assert "`migration`" in indice_pour("search", recherche("a.py", "b.py", "c.py"), ctx)
    assert indice_pour("search", recherche("a.py", "b.py"), ctx) == ""   # 2 fichiers : pas assez


def test_pas_d_indice_migration_sans_demande_de_migration():
    ctx = contexte("Corrige le bug du filtre batch.", ["search", "migrer_partout"])
    assert indice_pour("search", recherche("a.py", "b.py", "c.py"), ctx) == ""
