# Décisions du groupe

Dernière mise à jour : 2026-10-03. Les valeurs chiffrées sont dans `src/config.py`.

**Règle** : on n'efface jamais une ancienne décision de l'historique. Pour changer quelque chose,
on met à jour l'état courant dans le tableau des décisions et on ajoute une ligne à
l'historique en bas, avec la date et la raison, dans la même pull request que `config.py`.

Statuts : **Validé** (les deux), **À confirmer** (proposé, pas encore validé),
**Ouvert** (pas décidé).

## Décisions

| # | Décision | Valeur | Raison | Statut |
|---|---|---|---|---|
| 1 | Période chargée | du 1er déc. 2015 au 31 déc. 2025 | Décembre 2015 sert de marge pour les retards (jusqu'à 28 jours) | Validé |
| 2 | Découpage (jours cibles J+1) | Apprentissage 2016-2022 (2 557 jours) ; validation 2023 (365) ; test 2024-2025 (731) | Ordre chronologique ; validation = année la plus proche du test ; deux années de test pour juger la stabilité | Validé |
| 3 | Test bonus 2026 | Non retenu | Année incomplète, données consolidées encore changeantes. Peut être ajouté plus tard, à usage unique | À confirmer |
| 4 | Réestimation | Mensuelle, fenêtre qui grandit, uniquement des données antérieures au jour prédit | Suit les changements de niveau sans trop de calcul | Validé |
| 5 | Dernière consommation connue à 14 h | Valeur horaire étiquetée 12 (tranche 12 h-13 h) | Une valeur étiquetée 13 couvre 13 h-14 h et n'est pas complète à 14 h | Validé |
| 6 | Météo à 14 h | Dernière observation SYNOP dont l'heure locale est ≤ 13 h (12 h UTC l'hiver, 9 h UTC l'été). Dernière valeur connue, jamais d'interpolation vers le futur | Observations toutes les 3 h en UTC | Validé |
| 7 | Stations SYNOP | Sélection à redéfinir après analyse de l'ensemble des stations métropolitaines disponibles. Les 8 stations initiales restent un choix de référence à comparer | Le nombre et la liste des stations doivent être justifiés par leur couverture temporelle, la qualité des observations et leur répartition géographique plutôt que fixés a priori | Ouvert |
| 8 | Température nationale | Méthode d'agrégation à déterminer après l'analyse et la sélection des stations | La moyenne simple des 8 stations n'est plus fixée a priori. Les représentations pertinentes seront comparées avant de retenir une méthode | Ouvert |
| 9 | Covid | Retirer de l'apprentissage les jours cibles du 17 mars au 17 mai 2020 (62 jours). Valeurs gardées comme retards. Jamais en validation ni en test. 2022-2023 conservées | Régime exceptionnel ; une semaine de marge pour le retard de 168 h. Test de sensibilité à faire sur la validation | Validé |
| 10 | Heures manquantes | Interpolation linéaire, 3 heures de suite au plus, colonne `interpole` | Petits trous dus surtout au changement d'heure | À confirmer |
| 11 | Jours de 23 h et 25 h | Piste : grille UTC, prévision par heure locale, jours de changement d'heure traités à part et exclus des métriques principales | À décider ensemble | Ouvert |
| 12 | Benchmarks | B1 : même jour de la semaine précédente (J-6 pour la cible J+1). B2 : moyenne des 4 mêmes jours précédents | Sans apprentissage : le score à battre | Validé |
| 13 | Modèles | Référence apprise : régression calendrier + retards. Modèle simple : régression avec météo. Modèle élaboré : gradient boosting. Plafond : météo parfaite de J+1 (jamais présenté comme déployable) | Chaque modèle répond à une question précise | Validé |
| 14 | Forme des modèles | Régression linéaire : un modèle par heure cible. Gradient boosting : un seul modèle avec l'heure en variable, donc des variables définies relativement à l'heure cible (retard 24 h ou 48 h selon l'heure) | L'effet de la température diffère selon l'heure ; les arbres gèrent les interactions | À confirmer |
| 15 | Version des données de consommation | Définitives jusqu'en 2024, consolidées pour 2025 (à vérifier sur le jeu réel). Limite à écrire dans `docs/disponibilite_variables.md` | À 14 h, la valeur consolidée du jour n'existe pas encore | À confirmer |
| 16 | Format d'échange | Index `date_heure_utc` en UTC. Consommation : `consommation_MW` et `interpole`. Météo : `station` (code OMM texte), `date_heure_utc`, `t_celsius`. Calendrier calculé en heure de Paris | Permet de travailler en parallèle | À confirmer |

## Questions ouvertes

- Sélection des stations SYNOP : nombre et liste à déterminer après analyse de la couverture temporelle, des valeurs manquantes, de la qualité des observations et de la répartition géographique.
- Construction de l'information météorologique nationale : moyenne simple, pondération ou autre représentation à comparer après la sélection des stations.
- Résumé des vacances scolaires (zones A, B, C) : une variable par zone, ou le nombre de zones en vacances.
- Grille d'hyperparamètres du gradient boosting (à définir sur la validation seulement).
- Validation glissante (2021, 2022, 2023) en plus de 2023 : recommandée.
- Source de la consommation pour le pipeline : jeu en ligne ou fichiers annuels.

## Historique des changements

| Date | Changement | Raison |
|---|---|---|
| 2026-10-02 | Mise en ordre du dépôt : structure à plat, README court, `config.py`, ce fichier | Le README initial décrivait des fichiers inexistants et contredisait le CONTRIBUTING |
| 2026-10-02 | Stations : 11 → 8 | Choix du groupe |
| 2026-10-02 | Test bonus 2026 retiré (à confirmer) | Ne faisait pas partie du découpage retenu : test 2024-2025 |
| 2026-10-02 | Covid : dates précisées (17 mars au 17 mai 2020) | Remplace « mars à mai » |
| 2026-10-02 | Heure de 14 h reformulée : tranche 12 h-13 h (consommation), heure locale ≤ 13 h (météo) | Écriture sans ambiguïté |
| 2026-10-03 | Stations SYNOP : réouverture du choix de 8 stations | Le nombre et la liste des stations seront déterminés après analyse de leur couverture temporelle, de la qualité des observations et de leur répartition géographique |
| 2026-10-03 | Température nationale : méthode d'agrégation réouverte | La moyenne simple des 8 stations n'est plus fixée a priori ; la représentation nationale sera choisie après l'analyse des stations |
| 2026-10-03 | Dossiers renommés : `data/raw` → `data/donnees-brutes`, `data/processed` → `data/donnees-preparees` (`config.py` : `DATA_BRUTES`, `DATA_PREPAREES`) | Noms en français, plus clairs pour le groupe |
| 2026-10-03 | Source de la consommation : jeu en ligne `eco2mix-national-cons-def` (API ODRÉ). Il contient les données définitives jusqu'au 31/12/2024 et consolidées à partir du 01/01/2025 | Un seul jeu pour toute la période ; vérifié sur l'API le 2026-10-03. Répond à la question ouverte et à la décision 15 |