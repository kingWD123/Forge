---
name: ecriture-tests
description: Procédure quand la consigne demande d'écrire, d'ajouter ou de compléter des tests pour un module ou un comportement.
---
# Écrire des tests

N'écris pas ces tests toi-même : confie-les au **redacteur_tests**.

1. Donne-lui, dans une demande complète (il ne voit pas ta conversation) :
   - le module ou le comportement à couvrir ;
   - ce qui est attendu (couverture visée, cas à traiter) ;
   - les contraintes de la consigne (fichiers à ne pas toucher, etc.).
   Il n'écrit que dans tests/ et te rend la liste des tests ajoutés et des bugs
   qu'ils révèlent.
2. Lance ensuite la suite complète des tests.
3. S'il signale un bug et que la consigne ne demande que des tests, ne corrige
   pas le code : rapporte le bug à l'utilisateur.
