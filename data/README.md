# Données

Les données ne sont pas versionnées (voir `.gitignore`) : les scripts du dossier `src/` les
téléchargent ou les produisent. Seule exception : `resultats/` (scores et prévisions des modèles,
quelques Mo), versionné pour que le correcteur voie les résultats sans relancer 30 minutes de
calcul, et refait à l'identique par les commandes du README.

## Sources

| Donnée | Source | Remarque |
|---|---|---|
| Consommation | éCO2mix national (RTE), consommation en MW | Version définitive ou consolidée selon l'année : voir `docs/decisions.md` |
| Météo | SYNOP (Météo-France), jeu « Archive Synop OMM » sur data.gouv.fr : archives annuelles, liste des stations, postes | Heures en UTC. L'hôte cité par le catalogue (`meteofrance.object.data.gouv.fr`) n'existe plus : le code utilise `object.files.data.gouv.fr/meteofrance/` |
| Régions | Contours des régions (projet france-geojson, dérivé d'IGN Admin Express) | Sert à classer les stations par région |
| Consommation régionale | éCO2mix régional (RTE), `eco2mix-regional-cons-def`, 2016-2022 | Poids de la température pondérée ; la consommation nationale = somme exacte des 12 régions continentales (pas la Corse) |
| Calendrier | construit par le groupe | Jours fériés (`holidays`), vacances scolaires A, B, C (data.education.gouv.fr ; Bulletin officiel pour 2015-2017), ponts |

Tout se télécharge automatiquement : `python -m src.rte`, `python -m src.pipeline_meteo`,
`python -m src.calendrier`. Ensuite `python -m src.features` construit la table des variables
(ordre complet dans le README principal).

| Dossier | Contenu |
|---|---|
| `donnees-brutes/` | fichiers téléchargés, jamais modifiés |
| `interim/` | étapes intermédiaires de la consommation |
| `donnees-traitees/meteo/` | étapes de la météo : matrices, journaux, diagnostics, benchmarks |
| `donnees-preparees/` | fichiers finaux : `rte/`, `meteo/`, `calendrier/`, et `dataset_modelisation_2016_2025.csv` (table des variables à 14 h) |
| `resultats/` | scores et prévisions des modèles, comparaisons, analyses (versionné) |

## Constats de départ sur les fichiers de 2016 (2 octobre 2026)

Ces premiers constats ont été faits sur les fichiers de 2016, avant d'écrire les scripts. Ils sont
gardés comme historique ; chaque point indique ce qu'il est devenu. Les scripts traitent
aujourd'hui toutes les années, et les tests vérifient les fichiers produits.

**éCO2mix annuel définitif 2016 (fichier « .xls »)**
- C'est un fichier texte séparé par tabulations, en `latin-1`. Lecture :
  `pd.read_csv(f, sep="\t", encoding="latin-1", index_col=False)`. Sans
  `index_col=False`, les colonnes se décalent.
- La dernière ligne est un avertissement de RTE : à supprimer.
- 96 lignes par jour, mais la consommation n'est renseignée qu'à :00 et :30
  (48 valeurs par jour, 17 568 sur l'année). Les lignes :15 et :45 ne contiennent
  que des prévisions de RTE.
- Les colonnes « Prévision J-1 » et « Prévision J » sont des prévisions de RTE : pas de variables.
- Les 27 mars et 30 octobre 2016 ont aussi 96 lignes ; des valeurs sont recopiées le
  27 mars (02:00 et 03:00 identiques). **Devenu** : données stockées en UTC, lignes fantômes
  retirées, jours de changement d'heure jamais notés (décisions 10 et 11, `src/rte.py`).
- Le jeu en ligne `eco2mix-national-cons-def` a un format différent (date en UTC).
  **Devenu** : c'est la source retenue (historique de `docs/decisions.md`, 2026-10-03).

**SYNOP 2016 (`synop_2016_csv.gz`)**
- Séparateur `;`. Colonnes utiles : `geo_id_wmo` (texte, ex. `07149`), `validity_time`
  (UTC, ISO 8601), `t` (température en **kelvins**).
- Une observation toutes les 3 heures (0, 3, 6, ..., 21 h UTC) : 158 944 lignes, 60 stations.
- Valeurs manquantes : cellules **vides** (0,07 % pour `t`), pas `mq`.
- 58 doublons exacts, tous le 7 juillet 2016 à 12 h UTC : garder une ligne.
- Les colonnes `reference_time` et `insert_time` sont vides : le retard de publication
  ne peut pas se mesurer dans les données.
- Liste des stations : colonnes `ID` (entier : 7149), `Nom`, `Latitude`, `Longitude`, `Altitude`.
  Passer l'ID en texte de 5 caractères (`str(id).zfill(5)`) pour joindre avec `geo_id_wmo`.
  La métropole correspond aux ID inférieurs à 8000.
- Couverture 2016 des 8 stations envisagées au départ : de 2 861 à 2 927 observations sur
  2 928 attendues (Strasbourg est la moins complète). **Devenu** : le projet utilise 40 stations
  pour boucher les trous et 38 stations continentales pour la température France (décision 7) ;
  les 8 villes restent l'une des trois candidates (décision 8).
