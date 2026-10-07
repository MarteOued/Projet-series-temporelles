"""Textes du tableau de bord : fiches des méthodes et lexique.

Tous les chiffres affichés à côté de ces textes sont lus dans data/resultats/ :
ici, il n'y a que des explications, aucun résultat écrit à la main.
"""

FICHES = {
    "Benchmarks": {
        "methodes": ["B0", "B1", "B2"],
        "titre": "Les benchmarks : trois méthodes sans apprentissage",
        "idee": "Recopier le passé, sans rien apprendre. Ce sont les points de comparaison : un modèle "
                "qui ne fait pas mieux qu'eux ne sert à rien.",
        "sait": ["B0 : la consommation la plus récente connue à la même heure (la veille pour 0 h-12 h, "
                 "l'avant-veille pour 13 h-23 h)", "B1 : le même jour de la semaine précédente",
                 "B2 : la moyenne des 4 mêmes jours précédents"],
        "apprend": "Rien : aucun paramètre, aucune donnée d'apprentissage.",
        "reglage": "Aucun.",
        "forces": ["Suivent tout de suite le niveau récent de consommation (pas de biais).",
                   "Impossibles à « tricher » : on voit exactement ce qu'elles recopient."],
        "faiblesses": ["Ignorent la météo et les jours fériés : un lundi recopie un dimanche (B0), "
                       "un jour de froid recopie un jour doux."],
        "fichier": "src/benchmarks.py",
    },
    "M1": {
        "methodes": ["M1"],
        "titre": "M1 : le calendrier et la consommation passée",
        "idee": "Une régression linéaire : la prévision est une somme d'effets (effet du lundi, effet d'un "
                "jour férié, consommation de la veille…). Elle répond à la question : le calendrier et le "
                "passé suffisent-ils ?",
        "sait": ["consommation de la veille à la même heure (si H ≤ 12)", "consommation 48 h avant",
                 "consommation 7 jours avant", "jour de la semaine", "mois", "jour férié", "veille et lendemain de férié",
                 "pont", "vacances zones A, B, C"],
        "apprend": "24 régressions, une par heure de la journée : l'effet du lundi n'est pas le même à 4 h et à 19 h. "
                   "Réapprise au début de chaque mois avec tout le passé disponible, sans les jours du confinement.",
        "reglage": "Choix des retards et du calendrier sur 2023 (voir « Comment on a choisi »).",
        "forces": ["Simple, rapide, explicable : chaque effet est un nombre qu'on peut lire."],
        "faiblesses": ["Ne connaît pas la météo : se trompe dès qu'il fait plus froid ou plus chaud que les jours d'avant."],
        "fichier": "src/modeles_lineaires.py",
    },
    "M2": {
        "methodes": ["M2"],
        "titre": "M2 : M1 + la température — notre modèle retenu",
        "idee": "La même régression que M1, avec en plus la température de la France observée jusqu'à 13 h. "
                "Elle répond à la question : la météo aide-t-elle ?",
        "sait": ["tout ce que sait M1", "température à 13 h le jour J", "température moyenne de la veille",
                 "température lissée sur plusieurs jours (inertie des bâtiments)",
                 "degrés de chauffage : combien de degrés sous 15 °C", "degrés de climatisation : combien au-dessus de 22 °C"],
        "apprend": "24 régressions, une par heure, réapprises chaque mois, sans le confinement. La température est une "
                   "moyenne de 38 stations, pondérée par la consommation de chaque région.",
        "reglage": "Sur 2023 : 6 façons d'utiliser la température et 3 façons de calculer la température de la France "
                   "ont été comparées. Les 7 variables gagnent ; les 3 températures sont à égalité.",
        "forces": ["Le plus précis des modèles utilisables, et le meilleur en hiver.",
                   "Reste une régression : on peut expliquer chaque prévision."],
        "faiblesses": ["N'a pas de prévision météo : rate les redoux et les vagues de froid soudains.",
                       "Additionne les effets : un férié qui tombe un dimanche est prévu beaucoup trop bas.",
                       "A appris sur des années où l'on consommait plus : il prévoit un peu trop depuis 2023."],
        "fichier": "src/modeles_meteo.py",
    },
    "M3": {
        "methodes": ["M3"],
        "titre": "M3 : le gradient boosting",
        "idee": "Un modèle d'apprentissage automatique qui combine des centaines de petits arbres de décision "
                "« si… alors… ». Il a exactement les mêmes informations que M2 : seule la façon d'apprendre change. "
                "Il répond à la question : un modèle plus souple fait-il mieux ?",
        "sait": ["exactement les mêmes variables que M2"],
        "apprend": "24 modèles (un par heure), réappris chaque mois, sans le confinement, graine aléatoire fixée pour "
                   "obtenir toujours le même résultat.",
        "reglage": "4 réglages fixés à l'avance, comparés sur 2023 : le plus simple (arbres de 15 feuilles, "
                   "300 étapes, pas d'apprentissage 0,05) gagne.",
        "forces": ["Le meilleur en été et en automne.",
                   "Comprend les combinaisons : un dimanche férié n'est pas « dimanche + férié »."],
        "faiblesses": ["Pas meilleur que M2 au total : l'écart est dû au hasard.",
                       "Moins bon en hiver, et beaucoup moins facile à expliquer."],
        "fichier": "src/modeles_hgbr.py",
    },
    "M4": {
        "methodes": ["M4"],
        "titre": "M4 : M1 corrigé par ses erreurs récentes",
        "idee": "Si M1 s'est trompé hier, il se trompera peut-être aussi demain dans le même sens : M4 ajoute à M1 "
                "une correction tirée de ses erreurs passées (un modèle ARMA). Il répond à la question : les erreurs "
                "se répètent-elles ?",
        "sait": ["tout ce que sait M1", "erreur de M1 de la veille à la même heure (si H ≤ 12)",
                 "sinon, celle de l'avant-veille"],
        "apprend": "Un modèle de série temporelle sur les erreurs de M1, pour chaque heure, réappris chaque mois.",
        "reglage": "4 versions de l'ARMA comparées sur 2023 : la plus simple, un AR(1), gagne.",
        "forces": ["C'est le vrai modèle de série temporelle du projet, et son diagnostic est instructif."],
        "faiblesses": ["N'apporte rien : les erreurs ne se répètent qu'à 25 % d'un jour à l'autre, et plus du tout à deux jours.",
                       "Une petite fuite (l'heure 13) a été trouvée et corrigée : son test a été relancé."],
        "fichier": "src/modeles_arma.py",
    },
    "Plafond": {
        "methodes": ["Plafond"],
        "titre": "Le plafond « météo parfaite » : un repère, pas un modèle",
        "idee": "M2, mais avec la VRAIE température du lendemain. C'est impossible en vrai : à 14 h, personne ne "
                "connaît la météo exacte du lendemain. Il répond à la question : combien gagnerait-on avec une "
                "prévision météo parfaite ?",
        "sait": ["tout ce que sait M2", "température réelle de chaque heure du lendemain",
                 "température moyenne réelle du lendemain", "degrés de chauffage et de climatisation réels du lendemain"],
        "apprend": "Comme M2 : 24 régressions, réapprises chaque mois.",
        "reglage": "Aucun réglage propre : c'est M2 plus la vraie météo.",
        "forces": ["Mesure la valeur d'une prévision météo : de 17 % (2023) à 32 % (2026) d'erreur en moins que M2."],
        "faiblesses": ["Jamais utilisable pour prévoir : il triche volontairement, pour servir de repère."],
        "fichier": "src/analyses.py",
    },
}

LEXIQUE = [
    ("MW (mégawatt)", "Unité de puissance. La France consomme en moyenne environ 50 000 MW ; un réacteur nucléaire en produit 900 à 1 450."),
    ("GW (gigawatt)", "1 GW = 1 000 MW."),
    ("Erreur moyenne (MAE)", "Pour chaque heure prévue, on mesure de combien on s'est trompé, sans tenir compte du sens, puis on fait la moyenne."),
    ("RMSE", "Une autre erreur moyenne, qui punit plus fort les grosses erreurs."),
    ("Biais", "L'erreur moyenne avec son signe : positive si l'on prévoit trop en moyenne, négative si l'on prévoit trop peu."),
    ("Pointe", "Le moment de la journée où la consommation est la plus forte, souvent vers 19 h en hiver."),
    ("Benchmark", "Méthode très simple, sans apprentissage, qui sert de point de comparaison."),
    ("Régression linéaire", "Le modèle qui apprend le plus simple : la prévision est une somme d'effets."),
    ("Gradient boosting", "Un modèle d'apprentissage automatique qui combine beaucoup de petits arbres de décision."),
    ("ARMA, AR(1)", "Modèle de série temporelle : la valeur d'aujourd'hui dépend de celles des jours précédents. Un AR(1) ne regarde que la veille."),
    ("Apprentissage, validation, test", "On apprend sur 2016-2022, on choisit les réglages sur 2023, on juge sur 2024-2025 sans plus rien changer, puis une dernière fois sur début 2026."),
    ("Réestimation mensuelle", "Au début de chaque mois, le modèle réapprend avec toutes les données disponibles jusque-là."),
    ("Fuite d'information", "Utiliser par erreur une information du futur : la prévision paraît meilleure qu'elle ne l'est. Des tests automatiques l'empêchent."),
    ("Écart significatif", "Un écart trop grand pour être dû au hasard (moins de 5 % de chances, test de Diebold-Mariano)."),
    ("Degrés de chauffage", "Combien de degrés il fait sous 15 °C : 0 s'il fait plus de 15 °C, 5 s'il fait 10 °C."),
    ("Ablation", "Retirer un ingrédient d'un modèle pour mesurer ce qu'il apportait."),
]
