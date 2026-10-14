"""Banc de tâches de FORGE CODE.

Usage (depuis la racine du projet) :
  python -m bench.run verifier [jinja-001 ...]   vérifie que chaque tâche est bien construite
  python -m bench.run lancer   [jinja-001 ...]   lance l'Atelier sur les tâches et note le résultat
                                                 (--config A : sans Compilateur, --config B : avec)
  python -m bench.run web      jinja-001         prépare la tâche et ouvre l'interface adk web
  python -m bench.run juger    jinja-001         juge la tâche après son passage dans adk web

Sans identifiant, toutes les tâches de bench/tasks/ sont prises.

Une tâche (bench/tasks/*.yaml) contient :
  consigne      ce que reçoit l'agent (un symptôme, sans dire quel fichier corriger)
  injection     remplacements qui introduisent le problème dans le dépôt
  juge          arguments pytest qui doivent passer pour que la tâche soit réussie
  tests_caches  tests ajoutés seulement au moment de juger (l'agent ne les voit pas)
  solution      correction de référence ; par défaut, l'inverse de l'injection
  fichiers_autorises   (facultatif) seuls fichiers que l'agent a le droit de modifier
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

BENCH = Path(__file__).resolve().parent
RACINE = BENCH.parent
TRAVAIL = BENCH / "work"          # ignoré par git
RESULTATS = BENCH / "results"


# --------------------------------------------------------------------------- tâches

def charger_taches(ids: list[str]) -> list[dict]:
    fichiers = sorted((BENCH / "tasks").glob("*.yaml"))
    taches = [yaml.safe_load(f.read_text(encoding="utf-8")) for f in fichiers]
    if ids:
        return [t for t in taches if t["id"] in ids]
    # Sans identifiant : seulement les tâches actives (une tâche à revoir porte active: false).
    return [t for t in taches if t.get("active", True)]


def charger_depot(nom: str) -> dict:
    return yaml.safe_load((BENCH / "repos.yaml").read_text(encoding="utf-8"))[nom]


def appliquer(copie: Path, remplacements: list[dict]) -> None:
    """Applique des remplacements {fichier, avant, apres} ; chaque `avant` doit être unique."""
    for r in remplacements:
        fichier = copie / r["fichier"]
        texte = fichier.read_bytes().decode("utf-8")
        crlf = "\r\n" in texte
        texte = texte.replace("\r\n", "\n")
        nombre = texte.count(r["avant"])
        if nombre != 1:
            raise ValueError(f"{r['fichier']} : le texte à remplacer apparaît {nombre} fois (attendu : 1)")
        texte = texte.replace(r["avant"], r["apres"])
        if crlf:
            texte = texte.replace("\n", "\r\n")
        fichier.write_bytes(texte.encode("utf-8"))


def inverse(remplacements: list[dict]) -> list[dict]:
    return [{"fichier": r["fichier"], "avant": r["apres"], "apres": r["avant"]} for r in remplacements]


# ----------------------------------------------------------------------- préparation

def lancer(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kwargs)


def python_du_venv(venv: Path) -> Path:
    windows = venv / "Scripts" / "python.exe"
    return windows if windows.exists() else venv / "bin" / "python"


def preparer_depot(nom: str) -> tuple[Path, Path]:
    """Clone le dépôt au commit de référence et crée son environnement Python (une seule fois)."""
    depot = charger_depot(nom)
    source = TRAVAIL / "cache" / nom
    if not (source / ".git").exists():
        print(f"  clonage de {nom}...")
        lancer(["git", "clone", "-q", depot["url"], str(source)])
        lancer(["git", "checkout", "-q", depot["commit"]], cwd=source)
    venv = TRAVAIL / "venvs" / nom
    if not venv.exists():
        print(f"  création de l'environnement de {nom}...")
        lancer(["uv", "venv", "-q", str(venv)])
        lancer(["uv", "pip", "install", "-q", "--python", str(python_du_venv(venv)),
                *depot["dependances"]])
    return source, python_du_venv(venv)


def supprimer(dossier: Path) -> None:
    """Supprime un dossier, y compris les fichiers en lecture seule que git crée sous Windows."""
    def retirer_lecture_seule(fonction, chemin, _erreur):
        os.chmod(chemin, stat.S_IWRITE)
        fonction(chemin)
    shutil.rmtree(dossier, onexc=retirer_lecture_seule)


def preparer_copie(tache: dict, dossier: Path) -> Path:
    """Copie propre du dépôt, avec le problème de la tâche injecté puis commité.

    Le commit permet ensuite de voir avec git exactement ce que l'agent a modifié.
    """
    source, _ = preparer_depot(tache["depot"])
    copie = dossier / tache["id"]
    if copie.exists():
        supprimer(copie)
    shutil.copytree(source, copie)
    appliquer(copie, tache["injection"])
    git = ["git", "-c", "user.name=bench", "-c", "user.email=bench@forge"]
    lancer([*git, "add", "-A"], cwd=copie)
    # --allow-empty : les tâches de fonctionnalité n'injectent rien.
    lancer([*git, "commit", "-q", "--allow-empty", "-m", f"injection {tache['id']}"], cwd=copie)
    return copie


def environnement_de_test(tache: dict, copie: Path) -> dict:
    """Variables pour que les tests importent le code de la copie, pas une version installée."""
    depot = charger_depot(tache["depot"])
    return {**os.environ, "PYTHONPATH": str(copie.resolve() / depot["src"])}


# --------------------------------------------------------------------------- jugement

def pytest(tache: dict, copie: Path, arguments: list[str]) -> tuple[bool, str]:
    _, python = preparer_depot(tache["depot"])
    proc = subprocess.run([str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", *arguments],
                          cwd=copie, env=environnement_de_test(tache, copie), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)
    lignes = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    return proc.returncode == 0, (lignes[-1] if lignes else proc.stderr.strip()[-300:])


def fichiers_modifies(copie: Path) -> list[str]:
    """Fichiers modifiés ou créés depuis l'injection."""
    sortie = lancer(["git", "status", "--porcelain", "--untracked-files=all"], cwd=copie).stdout
    return sorted(ligne[3:].strip().strip('"') for ligne in sortie.splitlines() if ligne.strip())


def restaurer_tests_existants(tache: dict, copie: Path) -> list[str]:
    """Remet dans leur état d'origine les fichiers de tests existants que l'agent a modifiés
    ou supprimés : il ne doit pas pouvoir réussir en affaiblissant les tests.
    Les nouveaux fichiers de tests qu'il a créés sont conservés."""
    dossier_tests = charger_depot(tache["depot"])["tests"]
    sortie = lancer(["git", "diff", "--name-only", "HEAD", "--", dossier_tests], cwd=copie).stdout
    touches = [f.strip() for f in sortie.splitlines() if f.strip()]
    if touches:
        lancer(["git", "checkout", "HEAD", "--", *touches], cwd=copie)
    return touches


def juger(tache: dict, copie: Path) -> dict:
    modifies = fichiers_modifies(copie)   # avant d'ajouter les tests cachés

    tests_modifies = []
    if not tache.get("tests_modifiables"):   # vrai seulement pour les tâches d'écriture de tests
        tests_modifies = restaurer_tests_existants(tache, copie)

    # Régressions : la suite d'origine, sans les tests cachés de la tâche.
    for test in tache.get("tests_caches", []):
        (copie / test["fichier"]).unlink(missing_ok=True)
    suite_ok, suite_resume = pytest(tache, copie, [charger_depot(tache["depot"])["tests"]])

    for test in tache.get("tests_caches", []):
        chemin = copie / test["fichier"]
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(test["contenu"], encoding="utf-8")
    juge_ok, juge_resume = pytest(tache, copie, tache["juge"])

    autorises = tache.get("fichiers_autorises")
    interdits = [f for f in modifies if autorises and f not in autorises]

    return {
        "reussi": juge_ok and not interdits,
        "juge": juge_resume,
        "suite_complete": suite_resume,
        "regressions": not suite_ok,
        "fichiers_modifies": modifies,
        "tests_existants_modifies": tests_modifies,   # remis d'origine avant de juger
        "fichiers_interdits_modifies": interdits,
    }


# ------------------------------------------------------------------------- commandes

def verifier(taches: list[dict]) -> bool:
    """Une tâche est bien construite si le problème injecté fait échouer le juge,
    et si la solution de référence le fait repasser sans casser le reste."""
    dossier = TRAVAIL / "verification"
    tout_ok = True
    for tache in taches:
        copie = preparer_copie(tache, dossier)
        avant = juger(tache, copie)

        for test in tache.get("tests_caches", []):   # repartir sans les tests cachés
            (copie / test["fichier"]).unlink()
        appliquer(copie, tache.get("solution") or inverse(tache["injection"]))
        apres = juger(tache, copie)

        ok = not avant["reussi"] and apres["reussi"] and not apres["regressions"]
        tout_ok &= ok
        print(f"{'OK ' if ok else 'KO '} {tache['id']:<10} "
              f"injecté : {avant['juge']}  |  solution : {apres['juge']}"
              + ("" if not apres["regressions"] else f"  |  RÉGRESSIONS : {apres['suite_complete']}"))
    return tout_ok


# Configurations du protocole expérimental (dossier, section 7).
CONFIGURATIONS = {
    "A": {"FORGE_CONTEXT": "off"},   # agent de code simple
    "B": {"FORGE_CONTEXT": "on"},    # A + Compilateur de contexte
}


def environnement_atelier(tache: dict, copie: Path, mode: str, config: str = "A") -> dict:
    """Variables pour que l'Atelier travaille sur la copie, avec l'environnement Python du dépôt."""
    _, python = preparer_depot(tache["depot"])
    return {
        **environnement_de_test(tache, copie),
        **CONFIGURATIONS[config],
        "FORGE_WORKSPACE": str(copie),
        "FORGE_PERMISSION_MODE": mode,
        "FORGE_TEST_PYTHON": str(python),
        # "python" dans les commandes de l'agent désigne l'environnement du dépôt.
        "PATH": str(python.parent) + os.pathsep + os.environ["PATH"],
    }


def lancer_atelier(tache: dict, copie: Path, config: str) -> dict:
    """Lance l'Atelier dans un processus séparé, en mode auto, sur la copie du dépôt."""
    env = environnement_atelier(tache, copie, mode="auto", config=config)
    debut = time.time()
    proc = subprocess.run([sys.executable, "-m", "bench.atelier_runner", tache["consigne"]],
                          cwd=RACINE, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)
    lignes = proc.stdout.strip().splitlines()
    try:
        resultat = json.loads(lignes[-1])
    except (IndexError, json.JSONDecodeError):
        resultat = {"erreur": proc.stderr.strip()[-1000:]}
    resultat["duree_s"] = round(time.time() - debut)
    return resultat


def evaluer(taches: list[dict], config: str) -> None:
    """Lance l'Atelier sur chaque tâche, juge, et enregistre une ligne par tâche."""
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    RESULTATS.mkdir(exist_ok=True)
    fichier_resultats = RESULTATS / f"{run_id}-{config}.jsonl"
    print(f"Configuration {config} : {CONFIGURATIONS[config]}")
    statuts = []
    for tache in taches:
        print(f"> {tache['id']} ({tache['famille']})...", flush=True)
        copie = preparer_copie(tache, TRAVAIL / "runs" / run_id)
        agent = lancer_atelier(tache, copie, config)
        jugement = juger(tache, copie)

        # « erreur » : l'Atelier a été interrompu (quota, panne du modèle...) sans finir.
        # Ce n'est pas un échec de l'agent : la tâche est exclue du taux de résolution.
        if jugement["reussi"]:
            statut = "reussi"
        elif agent.get("erreur"):
            statut = "erreur"
        else:
            statut = "echec"
        statuts.append(statut)

        ligne = {"tache": tache["id"], "famille": tache["famille"], "configuration": config,
                 "statut": statut, **jugement, "agent": agent}
        with fichier_resultats.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        print(f"  {statut.upper():<7} juge : {jugement['juge']}"
              f"  |  appels d'outils : {len(agent.get('appels', []))}"
              f"  |  tokens : {agent.get('tokens_entree', 0) + agent.get('tokens_sortie', 0)}"
              f"  |  {agent['duree_s']} s"
              + ("  |  RÉGRESSIONS" if jugement["regressions"] else "")
              + (f"  |  tests remis d'origine : {', '.join(jugement['tests_existants_modifies'])}"
                 if jugement["tests_existants_modifies"] else "")
              + (f"  |  erreur : {agent['erreur'][:200]}" if agent.get("erreur") else ""))

    mesurees = [s for s in statuts if s != "erreur"]
    print(f"\nTaux de résolution : {statuts.count('reussi')}/{len(mesurees)}"
          f"  (+ {statuts.count('erreur')} interrompue(s) par une erreur, non comptée(s))"
          f"  ->  {fichier_resultats}")


def web(tache: dict, mode: str, port: int, config: str) -> None:
    """Prépare la tâche et ouvre l'interface adk web, réglée sur la copie du dépôt.

    Il reste à coller la consigne dans l'interface, puis à lancer `juger` pour le résultat.
    """
    copie = preparer_copie(tache, TRAVAIL / "web")
    print(f"\nTâche {tache['id']} prête dans : {copie}")
    print(f"Mode d'autorisation : {mode}  |  configuration {config} : {CONFIGURATIONS[config]}")
    print("\nConsigne à coller dans l'interface (agent « app ») :\n")
    print(f"    {tache['consigne']}\n")
    print(f"Quand l'Atelier a fini : python -m bench.run juger {tache['id']}")
    print(f"Ouvre http://localhost:{port} (Ctrl+C pour arrêter le serveur)\n", flush=True)
    adk = Path(sys.executable).parent / "adk"
    subprocess.run([str(adk), "web", "--port", str(port)], cwd=RACINE,
                   env=environnement_atelier(tache, copie, mode, config))


def juger_copie_web(tache: dict) -> None:
    """Juge la copie préparée par `web`, après le passage de l'Atelier."""
    copie = TRAVAIL / "web" / tache["id"]
    if not copie.exists():
        sys.exit(f"Pas de copie pour {tache['id']} : lance d'abord `python -m bench.run web {tache['id']}`.")
    jugement = juger(tache, copie)
    print(f"{'RÉUSSI' if jugement['reussi'] else 'ÉCHEC'}  {tache['id']}")
    print(f"  juge           : {jugement['juge']}")
    print(f"  suite complète : {jugement['suite_complete']}")
    print(f"  fichiers modifiés : {', '.join(jugement['fichiers_modifies']) or 'aucun'}")
    if jugement["fichiers_interdits_modifies"]:
        print(f"  fichiers interdits modifiés : {', '.join(jugement['fichiers_interdits_modifies'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commande", choices=["verifier", "lancer", "web", "juger"])
    parser.add_argument("taches", nargs="*", help="identifiants des tâches (toutes par défaut)")
    parser.add_argument("--mode", default="auto", choices=["ask", "auto-edit", "auto"],
                        help="mode d'autorisation pour `web` (auto par défaut)")
    parser.add_argument("--port", type=int, default=8001,
                        help="port de l'interface pour `web` (8001 par défaut, pour ne pas gêner un adk web déjà lancé)")
    parser.add_argument("--config", default="A", choices=sorted(CONFIGURATIONS),
                        help="configuration à mesurer pour `lancer` et `web` : A (sans Compilateur), B (avec)")
    args = parser.parse_args()
    taches = charger_taches(args.taches)

    if args.commande in ("web", "juger"):
        if len(taches) != 1:
            sys.exit(f"`{args.commande}` prend exactement une tâche, par exemple : jinja-001")
        if args.commande == "web":
            web(taches[0], args.mode, args.port, args.config)
        else:
            juger_copie_web(taches[0])
    elif args.commande == "verifier":
        sys.exit(0 if verifier(taches) else 1)
    else:
        evaluer(taches, args.config)


if __name__ == "__main__":
    main()
