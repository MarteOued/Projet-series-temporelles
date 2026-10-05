# Protocole de prévision

À 14 h (heure de Paris) le jour J, on prévoit les 24 valeurs horaires de consommation du jour J+1
(horizons de 10 h à 33 h). On n'utilise que ce qui était connu à cet instant.

## Ce qui est autorisé à 14 h le jour J

| Information | Autorisée ? | Pourquoi |
|---|---|---|
| Consommation des jours passés (J-1 et avant) | Oui | Entièrement connue |
| Consommation du jour J jusqu'à la tranche 12 h-13 h | Oui | Déjà publiée (hypothèse à vérifier) |
| Consommation du jour J après 13 h | Non | Pas encore publiée |
| Consommation de J+1 | Non | C'est la cible |
| Météo observée jusqu'à 13 h locale le jour J | Oui | Déjà mesurée |
| Météo observée de J+1 | Non en scénario opérationnel | N'existe pas encore |
| Calendrier de J+1 (jour, férié, vacances) | Oui | Connu à l'avance |
| Autres colonnes d'éCO2mix (production, échanges, CO2) | Non | Mesurées en même temps que la consommation |
| Prévisions de RTE | Pas comme variables | Comparaison externe possible, à signaler |

## Retards disponibles pour l'heure cible H du jour J+1

| Retard | Jour de référence | Disponible ? |
|---|---|---|
| 24 h | J, heure H | Oui seulement si H ≤ 12 |
| 48 h | J-1, heure H | Oui. Sert de « veille effective » quand H > 12 |
| 168 h | J-6, heure H (même jour de la semaine précédente) | Oui, toujours |

## Météo à 14 h (code : `src/protocole.py`, `src/temperature_france.py`)

- Les observations SYNOP sont toutes les 3 h en UTC (0, 3, 6, …, 21 h). À 14 h le jour J, on
  utilise la dernière observation dont l'heure locale est ≤ 13 h : **12 h UTC l'hiver,
  9 h UTC l'été** (`derniere_observation_synop_utilisable`). Marge d'une heure par prudence.
- Sur la grille horaire, la température **opérationnelle** de l'heure h est la dernière
  observation de validité ≤ h (report vers l'avant), **jamais une interpolation** : interpoler
  utiliserait l'observation suivante. Pour une prévision faite le jour J, on lit cette valeur à
  `limite_meteo_connue(J)` (13 h, heure de Paris).
- La version interpolée (`*_meteo_parfaite`) ne sert qu'au scénario « météo parfaite ».

## Transformations apprises sur les données

Tout ce qui est **appris** sur les données l'est uniquement sur la période d'apprentissage
(observations avant le 1er janvier 2023 à 0 h, heure de Paris : `protocole.fin_apprentissage_utc()`),
puis appliqué à toute la période. Cela concerne aujourd'hui :

| Quantité apprise | Où | Données utilisées |
|---|---|---|
| Corrélations, voisins et régressions entre stations (imputation spatiale) | `imputation_meteo.py` | 2015-12 à 2022 |
| Choix de la méthode d'imputation spatiale | `benchmark_imputation.py` | 2015-12 à 2022 |
| Choix de la méthode d'imputation temporelle (causale) par longueur de trou | `benchmark_imputation_temporelle.py` | 2015-12 à 2022 |
| Voisins, régressions et seuil de la règle d'anomalie | `correction_anomalies_meteo.py` | 2015-12 à 2022 |
| Poids régionaux de la température pondérée | `temperature_france.py` | consommation RTE 2016-2022 |

2023 sert aux choix de modélisation (validation) ; 2024-2025 ne sert à rien d'autre qu'à la note
finale. Les tests `tests/test_anti_fuite_meteo.py` vérifient que modifier 2023-2025 ne change
aucun de ces paramètres.

## Imputation de la météo : causale

Une température manquante à l'instant t n'est reconstruite qu'avec :
- les stations voisines **au même instant t** (imputation spatiale) ;
- ou, si tout le réseau est vide, **le passé** de la station : persistance, veille, ou persistance
  ajustée (imputation temporelle). Jamais l'observation suivante ni le lendemain.

## Heures

- Toutes les séries sont stockées en UTC. Le calendrier et l'origine de prévision sont calculés en heure de Paris.
- 14 h à Paris = 12 h UTC l'été, 13 h UTC l'hiver.
- Les jours de changement d'heure comptent 23 ou 25 heures : décision ouverte (voir `docs/decisions.md`).

## Deux scénarios

1. **Opérationnel** : uniquement l'information du tableau ci-dessus. C'est le seul présenté comme déployable.
2. **Météo parfaite** : ajoute la météo observée de J+1, uniquement comme borne de comparaison.

## Test de non-fuite (obligatoire avant toute modélisation)

Pour une origine donnée, on remplace toutes les données postérieures à l'origine par des valeurs
manquantes (ou du bruit), puis on reconstruit les variables. Elles doivent rester **exactement
identiques**. Si elles changent, une variable utilise une information inconnue à 14 h.

À ne pas utiliser comme variables d'entrée : une moyenne mobile centrée, une décomposition STL ajustée
sur toute la série, une normalisation calculée sur toutes les données, une interpolation qui regarde
l'observation suivante.
