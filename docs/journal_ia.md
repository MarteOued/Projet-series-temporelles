
# Journal de l'usage de l'IA

Le sujet autorise les agents conversationnels et les assistants de code. Le groupe reste néanmoins responsable du code, des choix méthodologiques, de l'absence de fuite d'information, de l'exactitude des résultats et de leur interprétation.

L'IA a été utilisée comme outil d'accompagnement pour comprendre le problème, proposer des solutions, développer et relire du code, identifier des erreurs et améliorer la documentation. Ses réponses n'ont pas été considérées comme des preuves : les propositions ont été confrontées aux données, aux tests ou aux résultats expérimentaux.

Chaque membre doit pouvoir expliquer les méthodes et les décisions prises lors de la soutenance.

**Règle de documentation :** conserver les usages notables, préciser les propositions acceptées, modifiées ou rejetées et indiquer leur méthode de vérification. Ne pas inventer d'interactions ni de résultats.

## 1. Historique des utilisations

| Date | Qui | Outil | Tâche demandée | Proposition obtenue | Décision | Vérification |
|---|---|---|---|---|---|---|
| 2026-10-03 | Martine | Claude | Comprendre pourquoi le notebook RTE ne s'exécutait pas | Le code était correct ; le kernel Python n'était pas sélectionné dans VS Code | Gardée | Exécution du notebook avec le `.venv` |
| 2026-10-03 | Martine | Claude | Expliquer le sujet et proposer une démarche | Plan en 10 étapes ; identification d'incohérences dans les noms de dossiers | Gardée et adaptée | Relecture du sujet et de `docs/decisions.md` |
| 2026-10-03 | Martine | Claude | Répartir le travail | Attribution initiale du calendrier à Martine | Rejetée | `CONTRIBUTING.md` attribue le calendrier à Khadim |
| 2026-10-03 | Martine | Claude | Construire le notebook RTE | Notebook commenté, avec certaines observations rédigées avant l'exécution | Modifiée | Commentaires corrigés après lecture des sorties réelles |
| 2026-10-03 | Martine | Claude | Choisir les données à télécharger | Ne télécharger que six colonnes et la période utile | Modifiée | Téléchargement du jeu complet : 508 320 lignes et 37 colonnes ; sélection ensuite |
| 2026-10-03 | Martine | Claude | Traiter les changements d'heure | Recalculer l'heure de Paris depuis l'UTC pour identifier les lignes fantômes | Gardée | Inspection des dates du 27/03/2016 et du 30/10/2016 ; `tests/test_rte.py` |
| 2026-10-03 | Martine | Claude | Représenter la consommation annuelle | Diagramme en barres avec un axe ne partant pas de zéro | Modifiée | Remplacement par des points reliés pour éviter une représentation trompeuse |
| 2026-10-03 | Martine | Claude | Documenter les données disponibles à 14 h | Définition du protocole et mesure des retards de publication | Gardée | Vérification sur l'API ODRÉ et `tests/test_protocole.py` |
| 2026-10-03 | Martine | Claude | Organiser le traitement RTE | Extraction des fonctions dans `src/rte.py` | Gardée | Résultat identique à celui du notebook ; 18 tests réussis |
| 2026-10-05 | Martine | Claude | Relire la météo et le calendrier de Khadim | Identification d'une fuite dans l'imputation, de stations corses hors périmètre et de lacunes documentaires | Gardée, transmise à Khadim | Pipeline relancé ; vérification du périmètre national |
| 2026-10-05 | Martine | Claude | Construire les benchmarks et les mesures d'erreur | `src/benchmarks.py`, `src/evaluation.py` et tests | Gardée | Calculs manuels et tests de la règle des 14 h |
| 2026-10-05 | Martine | Claude | Commenter la semaine du 16 janvier 2023 | Affirmation que les benchmarks suivaient bien la consommation | Modifiée | Le graphique montrait une sous-estimation pendant toute la semaine |
| 2026-10-05 | Martine | Claude | Ajouter le benchmark « jour précédent » | B0 : consommation de J jusqu'à l'heure 12, puis de J-1 | Gardée | Test de disponibilité des heures 12 et 13 |
| 2026-10-05 | Martine | Claude | Interpréter l'erreur horaire de B0 | Affirmation d'une erreur maximale le matin | Modifiée | L'erreur culmine plutôt vers 14–16 h |
| 2026-10-07 | Martine | Claude | Auditer les modèles M1 à M4 | Identification de problèmes de reproductibilité, de chronologie du test et d'une fuite dans M4 | Gardée | Reproduction des fichiers de résultats et inspection de l'historique Git |
| 2026-10-07 | Martine | Claude | Tester l'absence de fuite dans `features.py` | Perturber les données postérieures à 14 h et comparer les variables construites | Modifiée puis gardée | Introduction volontaire de fausses fuites pour contrôler le test |
| 2026-10-07 | Martine | Claude | Expliquer l'échec de M4 | Hypothèse d'erreurs d'apprentissage artificiellement petites | Rejetée | Écarts-types mesurés : 2 271 MW à l'apprentissage contre 2 063 MW en 2023 |
| 2026-10-07 | Martine | Claude | Commenter les résultats du notebook 04 | Commentaires anticipant un classement identique et un gain de facteur 2,5 | Modifiée | Vérification : certains classements s'inversent et le facteur est proche de 2,4 |
| 2026-10-07 | Martine | Claude | Préparer le test bonus 2026 | Étendre toute la période du projet jusqu'en juin 2026 | Rejetée | Test bonus isolé ; fichiers 2016–2025 identiques et scores reproduits |
| 2026-10-07 | Martine | Claude | Construire le tableau de bord Streamlit | Application à 12 pages | Modifiée | Inspection visuelle et tests automatisés des trois périodes |

## 2. Trois exemples détaillés — Martine

### 2.1. Proposition conservée : vérification de l'absence de fuite temporelle

**Tâche demandée :** vérifier que les variables produites par `src/features.py` n'utilisent aucune information postérieure à l'origine de prévision, fixée à 14 h le jour J.

**Proposition de l'IA :** construire les variables pour une date, modifier artificiellement les observations de consommation et de météo non disponibles à 14 h, puis reconstruire les mêmes variables. Si les résultats changent, une fuite d'information existe.

**Décision :** proposition conservée et intégrée aux tests.

**Vérification :** de fausses fuites ont été introduites volontairement. Une première modification météorologique n'était pas détectée, car elle concernait une fonction non utilisée par le calcul réel. Après avoir déplacé cette modification dans le chemin effectivement exécuté, le test l'a détectée. Une fausse fuite sur la consommation a également été détectée.

**Enseignement :** un test anti-fuite doit lui-même être testé pour démontrer son efficacité.

### 2.2. Proposition rejetée : extension de toute la période à 2026

**Tâche demandée :** préparer une évaluation complémentaire sur janvier–juin 2026.

**Proposition de l'IA :** prolonger la période principale du projet jusqu'au 30 juin 2026.

**Décision :** proposition rejetée, car le périmètre principal validé se termine au 31 décembre 2025.

**Solution retenue :** créer un mode de test bonus indépendant, sans modifier les données ni les configurations du projet principal.

**Vérification :** les fichiers 2016–2025 sont redevenus identiques à l'octet près, et le test bonus a reproduit les mêmes résultats.

**Enseignement :** une proposition techniquement réalisable peut être incompatible avec le protocole scientifique retenu.

### 2.3. Erreur détectée : commentaires anticipant les résultats

**Tâche demandée :** rédiger les interprétations du notebook d'évaluation.

**Proposition de l'IA :** plusieurs commentaires ont été produits avant l'examen des sorties, notamment un classement supposé identique entre 2024 et 2025 et une erreur annoncée 2,5 fois plus faible que celle de B0.

**Décision :** commentaires corrigés.

**Vérification :** confrontation systématique aux tableaux et aux graphiques. Les classements M1/M4 et B0/B1 s'inversent entre 2024 et 2025 ; le rapport d'erreur est d'environ 2,4.

Une autre explication proposée pour M4 a été rejetée après mesure : les erreurs d'apprentissage n'étaient pas plus petites que celles de validation.

**Enseignement :** l'IA peut produire des interprétations plausibles mais incompatibles avec les résultats observés.

## 3. Trois exemples détaillés — Khadim

Les exemples suivants décrivent des travaux documentés dans le projet. Leur attribution exacte à des échanges avec ChatGPT, ainsi que les décisions prises personnellement par Khadim, doivent être confirmées avant la remise.

### 3.1. Proposition conservée : imputation causale de la météo

**Tâche :** préparer une série de température nationale utilisable pour prévoir la consommation à 14 h, sans introduire d'information future.

**Travail documenté :** la préparation météorologique a nécessité de distinguer les observations disponibles, les valeurs manquantes et les températures du lendemain qui ne pouvaient pas être utilisées dans le scénario opérationnel.

Plusieurs solutions d'imputation ont été étudiées : exploitation des stations voisines au même instant, persistance, valeur de la veille et persistance ajustée.

**Décision méthodologique :** utiliser une imputation causale, reposant exclusivement sur des observations contemporaines disponibles ou sur le passé, et réserver les températures observées du lendemain au scénario théorique de météo parfaite.

**Vérification documentée :** des tests anti-fuite contrôlent que la modification d'observations futures ne change pas les valeurs imputées antérieurement. Les méthodes temporelles ont été comparées sur des séquences artificiellement masquées.

### 3.2. Proposition rejetée : seuil fixe pour les anomalies de température

**Tâche :** remplacer deux corrections manuelles d'anomalies de la météo par une règle automatique.

**Proposition de l'IA :** un seuil fixe de 10 °C d'écart entre une station et ses voisines.

**Décision :** proposition rejetée.

**Vérification :** ce seuil détectait aussi une vraie mesure, lors d'un orage. Il a été remplacé par un seuil appris sur l'apprentissage, de 14,19 °C.

**Enseignement :** une règle simple et plausible doit être testée sur des cas réels avant d'être retenue.

### 3.3. Proposition modifiée : correction autorégressive M4

**Tâche :** étudier si les erreurs récentes de M1 pouvaient améliorer les prévisions du lendemain.

**Travail documenté :** M4 applique une correction ARMA aux erreurs de M1. Une fuite temporelle a été détectée à l'heure 13 : le résidu du jour J n'était pas encore disponible au moment de la prévision.

**Décision méthodologique :** réserver le résidu de la veille aux heures 0 à 12 et utiliser celui de l'avant-veille pour les heures suivantes. Le modèle a été réévalué pour corriger cette erreur, sans procéder à un nouveau réglage sur le test.

**Vérification documentée :** `tests/test_modeles_arma.py` et reproduction des résultats. Les diagnostics montrent une faible persistance des erreurs, ce qui contribue à expliquer l'absence d'amélioration apportée par M4.


## 4. Autres exemples documentés — Notebook RTE

### 4.1. Proposition conservée : correction des lignes fantômes

L'agent a proposé de recalculer l'heure locale depuis l'UTC et de supprimer les lignes dont l'heure déclarée par RTE ne correspondait pas à l'heure recalculée.

**Vérification :** inspection manuelle des changements d'heure de 2016, suppression de 20 lignes fantômes sur dix ans et tests sur des données artificielles.

### 4.2. Proposition modifiée : téléchargement des données

L'agent recommandait de ne récupérer que les colonnes et les dates nécessaires.

Martine a choisi de conserver une extraction brute complète, puis de documenter les transformations successives.

**Vérification :** passage explicite de 37 à 5 colonnes et de 508 320 à 176 832 lignes.

### 4.3. Erreurs d'interprétation détectées

Certains commentaires générés avant l'exécution du notebook étaient inexacts : attribution de sauts de consommation à une heure erronée et identification injustifiée du confinement parmi les journées les plus atypiques.

**Décision :** réécriture des commentaires après consultation des données et des graphiques.

## 5. Corrections de la météo et du calendrier

Les corrections suivantes ont été demandées après la relecture du travail météorologique de Khadim, le 5 octobre 2026. Elles ont été réalisées par Martine avec Claude sur la branche `khadim/corrections-meteo`.

Ces interventions ne doivent pas être présentées comme des modifications directement effectuées par ChatGPT pour Khadim.

| Date | Intervention | Proposition | Décision | Vérification |
|---|---|---|---|---|
| 2026-10-05 | Rendre l'imputation temporelle causale | Persistance, veille et persistance ajustée selon la longueur du trou | Gardée | Tests anti-fuite et comparaison sur 1 000 séquences par longueur |
| 2026-10-05 | Remplacer deux corrections manuelles d'anomalies | Seuil fixe de 10 °C entre une station et ses voisines | Rejetée | Détectait aussi une vraie mesure lors d'un orage ; remplacement par un seuil appris de 14,19 °C |
| 2026-10-05 | Apprendre les paramètres météo sur l'apprentissage uniquement | Centraliser la limite temporelle dans `protocole.fin_apprentissage_utc()` | Gardée | Modification artificielle des données 2023 sans effet sur les coefficients |
| 2026-10-05 | Préparer plusieurs températures nationales | Trois candidates et deux scénarios : opérationnel et météo parfaite | Gardée | Modification des observations futures sans effet sur les valeurs opérationnelles antérieures |
| 2026-10-05 | Accélérer un benchmark temporel | Vectoriser la recherche des séquences | Gardée | Résultat identique sur 172 séquences ; temps réduit d'environ 10 minutes à 6 secondes |

La validation finale de ces corrections suppose leur relecture, leur exécution et leur compréhension par les membres du groupe.

## 6. Bilan critique

L'utilisation de l'IA a principalement apporté :

- une aide à la compréhension et à l'organisation du problème ;
- une assistance à la programmation et à la documentation ;
- des propositions de tests de cohérence et de non-fuite ;
- un soutien à l'analyse et à l'interprétation des résultats ;
- une aide à la reproductibilité et à la présentation du projet.

Plusieurs limites ont également été constatées :

- certaines propositions étaient incompatibles avec les décisions du groupe ;
- des commentaires ont été rédigés avant l'observation des résultats ;
- des explications statistiques plausibles se sont révélées fausses ;
- certains tests proposés ont nécessité eux-mêmes une vérification ;
- une solution correcte sur le plan informatique ne garantit pas le respect du protocole temporel.

Le groupe a donc retenu une démarche de vérification systématique : **proposition de l'IA, examen critique, test ou comparaison empirique, puis décision humaine documentée**.

L'IA a constitué un outil d'assistance, et non une source autonome de validation scientifique.
