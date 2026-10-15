"""Compilateur de contexte : indexation, sélection, compression, ordonnancement, éviction.

- etat.py       : état structuré de la tâche (objectif, contraintes épinglées, fichiers, décisions)
- indexer.py    : carte du dépôt (symboles, signatures, imports)
- selection.py  : fichiers et symboles utiles à la tâche
- assemblage.py : bloc de contexte compilé, ordonné, dans un budget fixe
- compiler.py   : before_model_callback qui assemble la requête et masque l'historique inutile
- troncature.py : after_tool_callback qui coupe les sorties trop longues (début + fin)
"""

from .compiler import compiler
from .etat import noter_decision
from .troncature import tronquer_sorties

__all__ = ["compiler", "noter_decision", "tronquer_sorties"]
