"""Tests de l'état structuré : objectif, contraintes épinglées, fichiers touchés, décisions."""

from types import SimpleNamespace

from google.adk.models import LlmRequest
from google.genai import types

from app.context.compiler import compiler
from app.context.etat import (CLE, afficher, est_une_relance, fichiers_touches_dans, lire,
                              mettre_a_jour, noter_decision)

ECRITURES = {"edit_file", "WriteFile"}


def test_objectif_et_contraintes_du_premier_message():
    state = {}
    etat = mettre_a_jour(state, "Migre billing vers Pydantic v2. Ne touche pas à l'API publique.", [])
    assert etat["objectif"].startswith("Migre billing")
    assert etat["contraintes"] == ["Ne touche pas à l'API publique."]
    assert state[CLE] == etat   # enregistré dans la session


def test_une_relance_garde_l_objectif_et_les_contraintes():
    # Le scénario du dossier : la contrainte du début reste valable plus tard.
    state = {}
    mettre_a_jour(state, "Migre billing vers Pydantic v2. Ne touche pas à l'API publique.", [])
    etat = mettre_a_jour(state, "Ok, continue avec le fichier suivant.", [])
    assert etat["objectif"].startswith("Migre billing")
    assert etat["contraintes"] == ["Ne touche pas à l'API publique."]
    assert etat["dernier_message"] == "Ok, continue avec le fichier suivant."


def test_les_contraintes_s_accumulent():
    state = {}
    mettre_a_jour(state, "Migre billing vers Pydantic v2. Ne touche pas à l'API publique.", [])
    etat = mettre_a_jour(state, "Passe maintenant au module invoices, sans modifier les tests.", [])
    assert etat["objectif"].startswith("Passe maintenant au module invoices")   # nouvelle tâche
    assert etat["contraintes"] == ["Ne touche pas à l'API publique.",
                                   "Passe maintenant au module invoices, sans modifier les tests."]


def test_meme_message_traite_une_seule_fois():
    state = {}
    mettre_a_jour(state, "Corrige le bug. Ne touche pas aux tests.", [])
    etat = mettre_a_jour(state, "Corrige le bug. Ne touche pas aux tests.", ["a.py"])
    assert etat["contraintes"] == ["Ne touche pas aux tests."]
    assert etat["fichiers_touches"] == ["a.py"]


def test_relances():
    assert est_une_relance("ok continue")
    assert est_une_relance("Vas-y, la suite.")
    assert not est_une_relance("Corrige le filtre batch qui regroupe mal les éléments.")
    assert not est_une_relance("Continue en migrant aussi le module invoices et ses dépendances vers v2.")


def test_seules_les_editions_reussies_comptent():
    def appel(id, chemin):
        return types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
            id=id, name="edit_file", args={"path": chemin}))])

    def reponse(id, contenu):
        return types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
            id=id, name="edit_file", response=contenu))])

    contents = [appel("1", "a.py"), reponse("1", {"status": "ok"}),
                appel("2", "b.py"), reponse("2", {"error": "old_string introuvable"})]
    assert fichiers_touches_dans(contents, ECRITURES) == ["a.py"]


def test_noter_decision():
    contexte = SimpleNamespace(state={})
    noter_decision("La cause est le .strip() dans compiler.py", contexte)
    assert lire(contexte.state)["decisions"] == ["La cause est le .strip() dans compiler.py"]


def test_affichage():
    state = {}
    mettre_a_jour(state, "Corrige le bug. Ne touche pas aux tests.", ["a.py"])
    noter_decision("La cause est dans a.py", SimpleNamespace(state=state))
    texte = afficher(lire(state))
    for attendu in ("Objectif : Corrige le bug.", "- Ne touche pas aux tests.",
                    "Fichiers déjà modifiés : a.py", "- La cause est dans a.py", "noter_decision"):
        assert attendu in texte
    assert afficher(lire({})) == ""


def test_compiler_garde_la_contrainte_apres_une_relance(monkeypatch):
    """Bout en bout : contrainte donnée au premier message, toujours en tête et en fin
    de requête après une relance « continue »."""
    monkeypatch.setenv("FORGE_CONTEXT", "on")
    contexte = SimpleNamespace(state={})

    def message(texte):
        return types.Content(role="user", parts=[types.Part(text=texte)])

    compiler(contexte, LlmRequest(contents=[message("Migre billing. Ne touche pas à l'API publique.")]))
    appel = types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
        id="1", name="search", args={"pattern": "x"}))])
    reponse = types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
        id="1", name="search", response={"r": "ok"}))])
    requete = LlmRequest(contents=[message("Migre billing. Ne touche pas à l'API publique."),
                                   message("Ok, continue."), appel, reponse])
    compiler(contexte, requete)

    assert "Ne touche pas à l'API publique." in str(requete.config.system_instruction)   # en tête
    rappel = requete.contents[-1].parts[-1].text                                        # à la fin
    assert rappel.startswith("<rappel_systeme>") and "ne la recopie pas" in rappel
    assert "Objectif : Migre billing." in rappel
    assert "Ne touche pas à l'API publique." in rappel
