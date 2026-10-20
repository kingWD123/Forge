"""Réglages communs aux tests.

L'Atelier lit FORGE_SPECIALISTES à son chargement, et .env peut le mettre à off : les tests
vérifient l'Atelier complet (configuration C). load_dotenv ne remplace pas une variable
déjà définie, donc ce réglage l'emporte sur .env.
"""

import os

os.environ["FORGE_SPECIALISTES"] = "on"
