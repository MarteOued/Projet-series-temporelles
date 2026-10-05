# Décisions du groupe

Dernière mise à jour : 2026-10-05. Les valeurs chiffrées sont dans `src/config.py`.

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
| 7 | Stations SYNOP | **Réseau d'imputation** : les 40 stations présentes chaque année 2015-2025 et situées dans les 13 régions métropolitaines (`src/meteo.py`). **Température France** : les 38 stations continentales (sans Ajaccio ni Bastia) | Beaucoup de stations aident à boucher les trous. La consommation nationale RTE ne couvre pas la Corse : elle est exactement la somme des 12 régions continentales (vérifié le 10/01/2023 à 18 h : 64 268 MW) | À confirmer |
| 8 | Température nationale | Trois candidates préparées, **aucune choisie** : `temp_8_villes`, `temp_38_simple`, `temp_38_ponderee` (moyenne par région, régions pondérées par leur part de consommation RTE 2016-2022). Choix sur la validation 2023 avec le modèle M2, jamais sur le test | Une moyenne simple surpondère les régions riches en stations (Occitanie 7 stations, 8,1 % de la consommation) face à l'Île-de-France (1 station, 14,8 %). La pondération est une candidate, à départager par les résultats | Ouvert (3 candidates prêtes) |
| 9 | Covid | Retirer de l'apprentissage les jours cibles du 17 mars au 17 mai 2020 (62 jours). Valeurs gardées comme retards. Jamais en validation ni en test. 2022-2023 conservées | Régime exceptionnel ; une semaine de marge pour le retard de 168 h. Test de sensibilité à faire sur la validation | Validé |
| 10 | Heures manquantes | Interpolation linéaire, 3 heures de suite au plus, colonne `interpole` | Petits trous dus surtout au changement d'heure | À confirmer |
| 11 | Jours de 23 h et 25 h | Piste : grille UTC, prévision par heure locale, jours de changement d'heure traités à part et exclus des métriques principales | À décider ensemble | Ouvert |
| 12 | Benchmarks | B1 : même jour de la semaine précédente (J-6 pour la cible J+1). B2 : moyenne des 4 mêmes jours précédents | Sans apprentissage : le score à battre | Validé |
| 13 | Modèles | Référence apprise : régression calendrier + retards. Modèle simple : régression avec météo. Modèle élaboré : gradient boosting. Plafond : météo parfaite de J+1 (jamais présenté comme déployable) | Chaque modèle répond à une question précise | Validé |
| 14 | Forme des modèles | Régression linéaire : un modèle par heure cible. Gradient boosting : un seul modèle avec l'heure en variable, donc des variables définies relativement à l'heure cible (retard 24 h ou 48 h selon l'heure) | L'effet de la température diffère selon l'heure ; les arbres gèrent les interactions | À confirmer |
| 15 | Version des données de consommation | Définitives jusqu'en 2024, consolidées pour 2025 (à vérifier sur le jeu réel). Limite à écrire dans `docs/disponibilite_variables.md` | À 14 h, la valeur consolidée du jour n'existe pas encore | À confirmer |
| 16 | Format d'échange | Index `date_heure_utc` en UTC. Consommation : `consommation_MW` et `interpole`. Météo : `station` (code OMM texte), `date_heure_utc`, `t_celsius`. Calendrier calculé en heure de Paris | Permet de travailler en parallèle | À confirmer |

## Questions ouvertes

- Température France : choisir entre les 3 candidates sur la validation 2023 (décision 8).
- Variable « période de Noël » (24 décembre - 1er janvier) : candidate, à évaluer sur 2023.
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
| 2026-10-05 | Imputation météo **causale** : une valeur manquante n'est reconstruite qu'avec les voisines au même instant ou le passé de la station (persistance, veille, persistance ajustée). Fin de l'interpolation et de la moyenne veille/lendemain | L'ancienne imputation utilisait l'observation suivante ou le lendemain : fuite d'information. Effet : 1 492 valeurs (0,13 %) changent de 2,0 °C en moyenne |
| 2026-10-05 | Tout paramètre appris sur la météo l'est sur la période d'apprentissage seulement (`protocole.fin_apprentissage_utc()`) : corrélations, voisins et régressions, choix des méthodes d'imputation, seuil d'anomalie, poids régionaux | Le test 2024-2025 ne doit servir à rien d'autre qu'à la note finale. Effet : les 9 793 valeurs imputées par les voisins changent de 0,04 °C en moyenne |
| 2026-10-05 | Méthode d'imputation temporelle choisie par longueur de trou sur l'apprentissage : persistance ajustée jusqu'à 4 points (12 h), veille au-delà ; règle valable pour toute longueur | Comparaison sur 1 000 séquences par longueur (1 à 16 points). Coût de la causalité : 1,48 °C contre 1,16 °C pour l'interpolation interdite (1 point), 2,29 °C contre 1,75 °C (8 points) |
| 2026-10-05 | Anomalies détectées par une règle au lieu de 2 dates écrites à la main : saut > 15 °C en 3 h ET écart aux voisines au même instant > plus grand écart vu sur l'apprentissage (14,19 °C) | La règle, appliquée sans connaître les dates, retrouve exactement MARIGNANE (2023-08-09 09 h UTC, 0 °C → 27,7 °C) et ST GIRONS (2025-09-23 15 h UTC, −11,3 °C → 13,7 °C). Un seuil fixe de 10 °C aurait aussi signalé une vraie mesure (orage du 13/08/2025) |
| 2026-10-05 | Calendrier : jours fériés calculés avec un jour de marge (le 31/12/2025 est bien veille de férié) ; variable candidate `periode_noel` | Bug de bord de période (jour du test). La période de Noël reste à évaluer sur 2023 |
| 2026-10-05 | Données météo retirées de Git (`data/donnees-traitees/` dans le `.gitignore`), reconstruites par `python -m src.pipeline_meteo` ; téléchargements automatiques (stations, postes, régions) ; nouvel hôte des archives SYNOP | `CONTRIBUTING.md` : les données ne sont pas versionnées. L'ancien hôte `meteofrance.object.data.gouv.fr` n'existe plus |
