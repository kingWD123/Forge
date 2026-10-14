"""Tests du Compilateur de contexte v1 (masquage des sorties et rappel de l'objectif)."""

from google.adk.models import LlmRequest
from google.genai import types

from app.context.compiler import compiler

GROS = "x" * 1000   # une sortie assez grosse pour être masquée


def consigne(texte):
    return types.Content(role="user", parts=[types.Part(text=texte)])


def appel(id, nom, **args):
    return types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(id=id, name=nom, args=args))])


def reponse(id, nom, contenu=GROS):
    return types.Content(role="user", parts=[
        types.Part(function_response=types.FunctionResponse(id=id, name=nom, response={"r": contenu}))])


def compiler_requete(contents, monkeypatch, actif="on"):
    monkeypatch.setenv("FORGE_CONTEXT", actif)
    requete = LlmRequest(contents=contents)
    compiler(None, requete)
    return requete.contents


def texte_reponse(content):
    return str(content.parts[0].function_response.response)


def test_desactive_par_defaut(monkeypatch):
    contents = [consigne("corrige"), appel("1", "ReadFile", path="a.py"), reponse("1", "ReadFile")]
    resultat = compiler_requete(list(contents), monkeypatch, actif="off")
    assert resultat == contents


def test_lecture_d_un_fichier_modifie_depuis_est_masquee(monkeypatch):
    contents = [
        consigne("corrige"),
        appel("1", "ReadFile", path="a.py", start_line=1, end_line=50), reponse("1", "ReadFile"),
        appel("2", "edit_file", path="a.py"), reponse("2", "edit_file", "ok"),
    ]
    resultat = compiler_requete(contents, monkeypatch)
    assert "fichier modifié depuis" in texte_reponse(resultat[2])
    assert "ReadFile a.py l.1-50" in texte_reponse(resultat[2])


def test_lecture_d_un_autre_fichier_est_gardee(monkeypatch):
    contents = [
        consigne("corrige"),
        appel("1", "ReadFile", path="b.py"), reponse("1", "ReadFile"),
        appel("2", "edit_file", path="a.py"), reponse("2", "edit_file", "ok"),
    ]
    resultat = compiler_requete(contents, monkeypatch)
    assert GROS in texte_reponse(resultat[2])


def test_ancien_run_tests_est_masque(monkeypatch):
    contents = [
        consigne("corrige"),
        appel("1", "run_tests"), reponse("1", "run_tests"),
        appel("2", "run_tests"), reponse("2", "run_tests"),
    ]
    resultat = compiler_requete(contents, monkeypatch)
    assert "run_tests plus récent" in texte_reponse(resultat[2])
    assert GROS in texte_reponse(resultat[4])   # le plus récent reste entier


def recherches(nombre):
    contents = [consigne("corrige")]
    for k in range(nombre):
        contents += [appel(str(k), "search", pattern=f"motif{k}"), reponse(str(k), "search")]
    return contents


def nombre_masquees(contents):
    return sum("sortie retirée" in texte_reponse(c) for c in contents if c.parts[0].function_response)


def test_vieilles_sorties_masquees_recentes_gardees(monkeypatch):
    # 17 sorties : 7 de trop par rapport aux 10 gardées -> un paquet de 5 masqué.
    resultat = compiler_requete(recherches(17), monkeypatch)
    reponses = [c for c in resultat if c.parts[0].function_response]
    assert all("ancienne" in texte_reponse(c) for c in reponses[:5])
    assert all(GROS in texte_reponse(c) for c in reponses[5:])


def test_masquage_par_paquets(monkeypatch):
    # Le masquage par âge n'avance que de 5 en 5 : le début de la requête reste
    # identique pendant plusieurs appels, ce qui préserve le cache du modèle.
    assert nombre_masquees(compiler_requete(recherches(14), monkeypatch)) == 0
    assert nombre_masquees(compiler_requete(recherches(15), monkeypatch)) == 5
    assert nombre_masquees(compiler_requete(recherches(19), monkeypatch)) == 5
    assert nombre_masquees(compiler_requete(recherches(20), monkeypatch)) == 10


def test_masquage_d_urgence_quand_le_contexte_est_trop_gros(monkeypatch):
    import sys
    module = sys.modules["app.context.compiler"]   # le module, pas la fonction du même nom
    monkeypatch.setattr(module, "SEUIL_URGENCE", 5_000)
    resultat = compiler_requete(recherches(8), monkeypatch)   # ~8 000 caractères
    reponses = [c for c in resultat if c.parts[0].function_response]
    assert all("contexte presque plein" in texte_reponse(c) for c in reponses[:5])
    assert all(GROS in texte_reponse(c) for c in reponses[5:])   # les 3 dernières restent


def test_petite_sortie_jamais_masquee(monkeypatch):
    contents = [
        consigne("corrige"),
        appel("1", "ReadFile", path="a.py"), reponse("1", "ReadFile", "court"),
        appel("2", "edit_file", path="a.py"), reponse("2", "edit_file", "ok"),
    ]
    resultat = compiler_requete(contents, monkeypatch)
    assert "court" in texte_reponse(resultat[2])


def test_objectif_rappele_a_la_fin(monkeypatch):
    contents = [consigne("Corrige le filtre batch."), appel("1", "search", pattern="batch"),
                reponse("1", "search", "court")]
    resultat = compiler_requete(contents, monkeypatch)
    dernier = resultat[-1]
    assert dernier.parts[0].function_response               # la réponse d'outil reste en tête
    assert "Corrige le filtre batch." in dernier.parts[-1].text


def test_pas_de_rappel_avant_le_premier_outil(monkeypatch):
    contents = [consigne("Corrige le filtre batch.")]
    resultat = compiler_requete(contents, monkeypatch)
    assert len(resultat) == 1 and len(resultat[0].parts) == 1


def test_historique_de_la_session_intact(monkeypatch):
    lecture = reponse("1", "ReadFile")
    contents = [consigne("corrige"), appel("1", "ReadFile", path="a.py"), lecture,
                appel("2", "edit_file", path="a.py"), reponse("2", "edit_file", "ok")]
    compiler_requete(contents, monkeypatch)
    assert GROS in texte_reponse(lecture)   # l'objet d'origine n'a pas été modifié
