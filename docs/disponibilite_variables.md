# Tableau de disponibilité des variables (brouillon)

Question à laquelle chaque ligne répond : *cette prévision aurait-elle réellement pu être calculée à 14 h le jour J ?*
À compléter et à vérifier au fil du projet (une colonne « Statut » indique où en est chaque ligne).

| Variable | Source | Disponible à 14 h le jour J ? | Observé ou prévu | Utilisation | Risque de fuite | Statut |
|---|---|---|---|---|---|---|
| Consommation de J jusqu'à la tranche 12 h-13 h | éCO2mix | Oui. Le temps réel est publié toutes les 15 min, en ligne environ 11 à 13 min après la fin du quart d'heure (2 mesures, 3/10/2026). La tranche 13 h-14 h n'est pas complète à 14 h | Observé | Retard 24 h (H ≤ 12), niveau récent | Notre historique est la version consolidée ou définitive, plus propre que le temps réel disponible à 14 h (écart non mesurable : RTE efface le temps réel) | Vérifié (notebook 01, étape 11 ; `src/protocole.py` ; `tests/test_protocole.py`) |
| Consommation de J-1 et avant | éCO2mix | Oui | Observé | Retards 48 h et 168 h, moyennes | Faible. Même limite de version : 2025 est consolidée, pas définitive | Vérifié (même source) |
| Consommation de J+1 | éCO2mix | Non | Observé a posteriori | Cible et évaluation seulement | Fuite si utilisée comme entrée | Interdit |
| Température France observée jusqu'à 13 h locale de J (3 candidates : 8 villes, 38 simple, 38 pondérée) | SYNOP, 38 stations continentales | Oui : dernière observation à 12 h UTC (hiver) ou 9 h UTC (été) ; insérées quelques minutes après leur heure d'observation (audit 2025, à confirmer sur l'historique où `insert_time` est vide) | Observé | Modèle simple, gradient boosting | Valeurs imputées : causales (voisins au même instant ou passé), paramètres appris sur 2016-2022 ; grille horaire par report, jamais d'interpolation | Vérifié par les tests anti-fuite |
| Température observée pendant J+1 | SYNOP | Non | Observé a posteriori | Scénario « météo parfaite » seulement | Fuite en scénario opérationnel | Interdit hors plafond |
| Heure, jour de la semaine, mois, week-end | Calendrier | Oui | Connu à l'avance | Tous les modèles | Nulle | Validé |
| Jours fériés, ponts, vacances scolaires, période de Noël (candidate) | Calendriers publics (`holidays`, data.education.gouv.fr, Bulletin officiel pour 2015-2017) | Oui, publiés à l'avance | Connu à l'avance | Tous les modèles | Faible (décisions tardives) | Construit (`src/calendrier.py`) |
| Autres colonnes d'éCO2mix | éCO2mix | Non | Observé | Aucune | Production ajustée à la consommation | Interdit |
| Prévisions de consommation de RTE | éCO2mix | À vérifier | Prévu | Comparaison seulement | Instant de publication à confirmer | Exclu des variables |

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
