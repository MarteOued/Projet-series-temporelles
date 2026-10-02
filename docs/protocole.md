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
