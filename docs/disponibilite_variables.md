# Tableau de disponibilité des variables (brouillon)

Question à laquelle chaque ligne répond : *cette prévision aurait-elle réellement pu être calculée à 14 h le jour J ?*
À compléter et à vérifier au fil du projet (une colonne « Statut » indique où en est chaque ligne).

| Variable | Source | Disponible à 14 h le jour J ? | Observé ou prévu | Utilisation | Risque de fuite | Statut |
|---|---|---|---|---|---|---|
| Consommation de J jusqu'à la tranche 12 h-13 h | éCO2mix | Oui, après un délai de publication | Observé | Retard 24 h (H ≤ 12), niveau récent | Version consolidée plus propre que le temps réel | À vérifier |
| Consommation de J-1 et avant | éCO2mix | Oui | Observé | Retards 48 h et 168 h, moyennes | Faible. 2025 est consolidée, pas définitive | À vérifier |
| Consommation de J+1 | éCO2mix | Non | Observé a posteriori | Cible et évaluation seulement | Fuite si utilisée comme entrée | Interdit |
| Température observée jusqu'à 13 h locale de J | SYNOP | Oui, délai à vérifier | Observé | Modèle simple, gradient boosting | Heures en UTC ; jamais d'interpolation vers le futur | À vérifier |
| Température observée pendant J+1 | SYNOP | Non | Observé a posteriori | Scénario « météo parfaite » seulement | Fuite en scénario opérationnel | Interdit hors plafond |
| Heure, jour de la semaine, mois, week-end | Calendrier | Oui | Connu à l'avance | Tous les modèles | Nulle | Validé |
| Jours fériés, ponts, vacances scolaires | Calendriers publics | Oui, publiés à l'avance | Connu à l'avance | Tous les modèles | Faible (décisions tardives) | À construire |
| Autres colonnes d'éCO2mix | éCO2mix | Non | Observé | Aucune | Production ajustée à la consommation | Interdit |
| Prévisions de consommation de RTE | éCO2mix | À vérifier | Prévu | Comparaison seulement | Instant de publication à confirmer | Exclu des variables |
