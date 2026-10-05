# Journal de l'usage de l'IA

Le sujet autorise les agents conversationnels et les assistants de code, mais le groupe reste responsable
du code, des méthodes, de l'absence de fuite, de l'exactitude des résultats et de l'interprétation.
Chacun doit pouvoir tout expliquer à l'oral.

**À tenir au fil de l'eau** : une ligne par usage notable, remplie le jour même. Ne rien inventer.

| Date | Qui | Outil | Tâche demandée | Proposition obtenue | Décision (gardée, modifiée, rejetée) | Comment on a vérifié |
|---|---|---|---|---|---|---|
| 2026-10-03 | Martine | Claude Code | Comprendre pourquoi le notebook RTE ne s'exécutait pas | Le code était correct ; le problème venait du kernel non sélectionné dans VS Code | Gardée | Notebook exécuté en ligne de commande avec le `.venv` : il tournait |
| 2026-10-03 | Martine | Claude Code | Expliquer le sujet et proposer une démarche | Plan en 10 étapes, cohérent avec `docs/decisions.md` ; repérage de noms de dossiers incohérents (`raw` / `donnees-brutes`) | Gardée, puis corrigée (voir ligne suivante) | Relecture du sujet et des docs du dépôt |
| 2026-10-03 | Martine | Claude Code | Répartition du travail | L'agent a d'abord attribué le calendrier à Martine | Rejetée | `CONTRIBUTING.md` attribue le calendrier à Khadim ; erreur relevée par l'agent lui-même en relisant le fichier |
| 2026-10-03 | Martine | Claude Code | Écrire le notebook RTE en 10 étapes, commenté | Notebook complet ; commentaires d'observation écrits **avant** l'exécution | Modifiée | Après exécution, deux commentaires ne correspondaient pas aux données (voir exemple 3) : corrigés d'après les sorties réelles |
| 2026-10-03 | Martine | Claude Code | Choix des données téléchargées | Télécharger seulement 6 colonnes et la période utile | Modifiée à la demande de Martine | Tout le jeu est téléchargé (508 320 lignes, 37 colonnes), puis la sélection est faite et justifiée dans le code |
| 2026-10-03 | Martine | Claude Code | Traiter les changements d'heure | Règle des « lignes fantômes » : heure de Paris recalculée depuis l'UTC et comparée à l'heure écrite par RTE | Gardée | Lignes de l'API du 27/03/2016 et du 30/10/2016 inspectées à la main ; plus aucun doublon ; tests `tests/test_rte.py` |
| 2026-10-03 | Martine | Claude Code | Graphique de la consommation par année | Barres avec un axe ne partant pas de 0 | Modifiée | Une barre doit partir de 0 ; remplacé par des points reliés |
| 2026-10-03 | Martine | Claude Code | Documenter la disponibilité des données à 14 h | Section 11 du notebook, `src/protocole.py`, retard de publication mesuré sur l'API (11 à 13 min) | Gardée | Tableau des retards calculé et vérifié automatiquement ; `tests/test_protocole.py` ; descriptions officielles des jeux ODRÉ |
| 2026-10-03 | Martine | Claude Code | Déplacer le code du notebook dans `src/rte.py` | Fonctions par étape, notebook qui les appelle | Gardée | `python -m src.rte` produit un fichier identique ligne à ligne à celui du notebook ; 18 tests passent |
| 2026-10-05 | Martine | Claude Code | Relire le travail météo et calendrier de Khadim | Bilan : calcul reproductible, mais fuite d'information dans l'imputation temporelle, stations corses hors périmètre, documentation incomplète | Gardée, transmise à Khadim | Pipeline relancé depuis les données brutes (18 fichiers identiques) ; périmètre vérifié : conso nationale = somme exacte des 12 régions continentales |
| 2026-10-05 | Martine | Claude Code | Écrire les benchmarks B1, B2 et les mesures d'erreur | `src/benchmarks.py`, `src/evaluation.py`, tests, notebook 03 | Gardée | Tests sur des exemples calculables à la main ; règle des 14 h vérifiée pour chaque jour, et test qu'une triche est bien détectée |
| 2026-10-05 | Martine | Claude Code | Commenter le graphique de la semaine du 16 janvier 2023 | Commentaire écrit : « en début de semaine, les benchmarks suivent bien » | Modifiée | En regardant le graphique, les benchmarks sont trop bas toute la semaine (semaine précédente plus douce) : commentaire corrigé |

## Les trois exemples exigés dans le rapport

Brouillons à relire et à reformuler par le groupe.

1. **Proposition conservée après vérification** : la règle des « lignes fantômes » des jours de
   passage à l'heure d'été. *Tâche* : supprimer les doublons d'instants UTC. *Proposition* :
   recalculer l'heure de Paris depuis l'instant UTC et supprimer les lignes où elle diffère de
   l'heure écrite par RTE. *Décision* : gardée. *Vérification* : lignes de l'API inspectées à la
   main (le « 02:00 » du 27/03/2016 recopie une autre valeur), 20 lignes supprimées, une par
   heure fantôme sur 10 ans, plus aucun doublon, tests sur de fausses données.
2. **Proposition modifiée ou rejetée** : l'agent proposait de ne télécharger que les colonnes
   et la période utiles. Martine a demandé de télécharger tout le jeu pour voir sa taille réelle
   et garder une donnée brute intacte. *Décision* : modifiée. *Vérification* : la sélection
   (37 → 5 colonnes, 508 320 → 176 832 lignes) est maintenant visible et justifiée étape par étape.
3. **Erreur, faiblesse ou réponse trompeuse détectée** : dans le notebook, l'agent avait écrit
   des commentaires d'observation avant d'avoir les résultats. Deux étaient faux : les sauts
   brutaux étaient attribués aux chauffe-eau à 23 h, alors qu'ils tombent à 19 h deux dimanches
   de février ; le confinement de 2020 était annoncé parmi les jours les plus atypiques, alors
   que la méthode (écart à la médiane du mois) ne peut pas le détecter. *Décision* : commentaires
   réécrits d'après les sorties réelles. *Vérification* : lecture des sorties et des graphiques.

Pour chaque exemple : la tâche demandée, la proposition obtenue, la décision prise, la méthode de vérification.
