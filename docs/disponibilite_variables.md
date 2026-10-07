# Tableau de disponibilité des variables

Question à laquelle chaque ligne répond : *cette prévision aurait-elle réellement pu être calculée à 14 h le jour J ?*
Les variables des modèles sont construites par `src/features.py` (une ligne par jour cible J+1 et
par heure H). Le test `tests/test_features.py` remplace par des valeurs absurdes tout ce qui suit
14 h le jour J et vérifie qu'aucune variable ne change.

## Variables utilisées par les modèles

| Variable (colonne du dataset) | Source | Disponible à 14 h le jour J ? | Observé ou prévu | Modèles | Risque de fuite | Statut |
|---|---|---|---|---|---|---|
| `conso_veille_effective_MW` : consommation 24 h avant l'heure cible si H ≤ 12, sinon 48 h avant (`retard_effectif_h`) | éCO2mix | Oui : pour H ≤ 12, la tranche H du jour J est finie avant 13 h. La tranche 13 h-14 h n'est pas complète à 14 h | Observé | M1 à M4, plafond | Notre historique est la version consolidée ou définitive (voir plus bas) | Vérifié (`tests/test_features.py`, `tests/test_protocole.py`) |
| `conso_lag48_MW`, `conso_lag168_MW` : consommation 48 h et 7 jours avant l'heure cible | éCO2mix | Oui | Observé | M1 à M4, plafond | Même limite de version | Vérifié (mêmes tests) |
| Résidu de M1 de la veille (M4) : seulement pour H ≤ 12 ; sinon celui de l'avant-veille | éCO2mix et M1 | Oui | Observé | M4 | **Fuite corrigée le 2026-10-07** : l'heure 13 utilisait la tranche 13 h-14 h du jour J | Vérifié (`tests/test_modeles_arma.py`) |
| `temp_38_ponderee_origine` : température France à 13 h locale le jour J | SYNOP, 38 stations continentales | Oui : dernière observation à 12 h UTC (hiver) ou 9 h UTC (été), reportée heure par heure | Observé | M2, M3, plafond | Valeurs imputées de façon causale (voisins au même instant ou passé), paramètres appris sur 2016-2022 ; jamais d'interpolation vers le futur | Vérifié (`tests/test_features.py`, `tests/test_anti_fuite_meteo.py`) |
| `temp_38_ponderee_veille` : moyenne du jour J-1 complet | SYNOP | Oui | Observé | M2, M3, plafond | Faible | Vérifié |
| `temp_38_ponderee_lissee` : lissage exponentiel (alpha = 0,5) des moyennes journalières, le jour J ne comptant que jusqu'à 13 h | SYNOP | Oui | Observé | M2, M3, plafond | Faible | Vérifié |
| Degrés de chauffage et de climatisation (seuils 15 °C et 22 °C), à l'origine et lissés | Calculés à partir des lignes ci-dessus | Oui | Observé | M2, M3, plafond | Seuils fixés à l'avance (notebook 02, 2016-2022) | Vérifié |
| Jour de la semaine, mois du jour cible | Calendrier | Oui | Connu à l'avance | Tous | Nulle | Validé |
| `ferie`, `veille_ferie`, `lendemain_ferie`, `pont_potentiel`, `vacances_A`, `vacances_B`, `vacances_C` du jour cible | `holidays`, data.education.gouv.fr, Bulletin officiel (2015-2017) | Oui, publiés à l'avance | Connu à l'avance | Tous | Faible (décisions tardives, ex. pont décidé tard) | Validé (`src/calendrier.py`) |

## Variables non utilisées ou interdites

| Variable | Pourquoi |
|---|---|
| Consommation de J+1 | C'est la cible : utilisée seulement pour apprendre et noter |
| Consommation du jour J après la tranche 12 h-13 h | Pas encore publiée à 14 h |
| Température observée pendant J+1 (`*_meteo_parfaite`) | Inconnue à 14 h. Utilisée **seulement** par le plafond « météo parfaite » (`src/analyses.py`), jamais présenté comme une prévision possible ; `features.construire_dataset` refuse ces colonnes |
| Prévision météo de J+1 | Elle existe à 14 h (Météo-France), mais nous n'avons pas son historique. C'est la principale piste d'amélioration (3 pires jours, notebook 04) |
| `weekend`, `nb_zones_vacances`, `periode_noel` | Disponibles, mais non retenues : `weekend` est déjà contenu dans le jour de la semaine ; les deux autres n'apportent rien sur 2023 (ablation du calendrier) |
| Autres colonnes d'éCO2mix (production, échanges) | La production s'ajuste à la consommation : ce serait une fuite indirecte |
| Prévisions de consommation de RTE | Instant de publication non vérifié : exclues des variables |

## Les trois versions de la consommation RTE

D'après les descriptions officielles des jeux de données sur ODRÉ (consultées le 3/10/2026) :

| Version | Pas de temps | Publication | Jeu de données |
|---|---|---|---|
| Temps réel | 15 min | en continu, mise à jour toutes les 15 min | `eco2mix-national-tr` |
| Consolidée | 30 min | milieu du mois M+1 | `eco2mix-national-cons-def` |
| Définitive | 30 min | second semestre de l'année A+1 | `eco2mix-national-cons-def` |

À 14 h le jour J, seule la version temps réel existe pour J et les jours récents. Nous rejouons
le passé avec les versions consolidée et définitive, car RTE remplace le temps réel par ces
versions : nous respectons **quelles heures** étaient connues, pas **quelle version**. Limite à
écrire dans le rapport (erreurs probablement un peu optimistes).
