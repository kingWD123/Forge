"""Outils d'orchestration : des outils que l'Atelier appelle comme les autres, mais qui
déroulent en code un processus fixe et lancent eux-mêmes des sous-agents.

Les outils simples, qui agissent directement sur le dépôt, sont dans app/tools ;
les agents, dans app/sub_agents.

- migrer_partout : un migrateur par fichier, puis vérification qu'il ne reste plus l'ancien code.
"""
