# FORGE CODE

Agent de code en terminal construit avec Google ADK. L'agent principal, **l'Atelier**, compile son contexte et forge ses propres sous-agents quand une tâche dépasse un seul contexte.

## Lancer

```bash
gcloud auth application-default login
cp .env.example .env   # puis renseigner GOOGLE_CLOUD_PROJECT
adk run app
```

## Structure

```
app/
  agent.py, prompt.py   l'Atelier (root_agent)
  tools/                read_file, search, edit_file, bash, run_tests, git
  context/              Compilateur de contexte
  agents_forges/        fiche d'un sous-agent forgé (schéma) et chargeur -> LlmAgent
  registry.py           Registre .forge/agents
  sub_agents/
    evaluateur/         décide s'il faut déléguer
    forgeron/           conçoit un sous-agent (Agent Config YAML)
    banc_essai/         teste un sous-agent forgé (LoopAgent, 3 essais max)
    verificateur/       tests + revue du diff
eval/                   évaluation ADK
tests/
deployment/
.forge/agents/          sous-agents forgés
.forge/skills/          skills forgées pour le dépôt
```
