---
name: migration
description: Procédure quand la consigne demande de renommer, migrer ou remplacer quelque chose dans tout le dépôt (un nom, une API, un import). Pas pour corriger un bug ni pour modifier des tests.
---
# Migrer dans tout le dépôt

Ne fais pas ces modifications toi-même, fichier par fichier : c'est long, coûteux,
et on oublie facilement une occurrence cachée (dans une chaîne, une liste
d'exports, du code généré, un commentaire).

1. Appelle **migrer_partout**, une seule fois. Donne-lui :
   - l'ancien code et le nouveau (ex. `internalcode` → `mark_internal`) ;
   - la règle, avec un exemple ;
   - dans `exclure` : les fichiers que la consigne interdit de modifier, et les tests.
   Il trouve les fichiers concernés, confie chacun à un migrateur et vérifie qu'il
   ne reste plus l'ancien code.
2. Lis son rapport. S'il signale des occurrences restantes ou des incertitudes,
   traite-les toi-même avec edit_file, une par une.
3. Vérifie avec search que l'ancien code a disparu (hors fichiers exclus).
4. Lance la suite complète des tests.

Pour appliquer une règle à **un seul** fichier précis, appelle plutôt le migrateur
directement, avec le chemin du fichier, la règle et un exemple.
