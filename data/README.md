# Données

Aucune donnée n'est versionnée (voir `.gitignore`) : les scripts du dossier `src/` les
téléchargent ou les produisent.

## Sources

| Donnée | Source | Remarque |
|---|---|---|
| Consommation | éCO2mix national (RTE), consommation en MW | Version définitive ou consolidée selon l'année : voir `docs/decisions.md` |
| Météo | SYNOP (Météo-France), jeu « Archive Synop OMM » sur data.gouv.fr : archives annuelles, liste des stations, postes | Heures en UTC. L'hôte cité par le catalogue (`meteofrance.object.data.gouv.fr`) n'existe plus : le code utilise `object.files.data.gouv.fr/meteofrance/` |
| Régions | Contours des régions (projet france-geojson, dérivé d'IGN Admin Express) | Sert à classer les stations par région |
| Consommation régionale | éCO2mix régional (RTE), `eco2mix-regional-cons-def`, 2016-2022 | Poids de la température pondérée ; la consommation nationale = somme exacte des 12 régions continentales (pas la Corse) |
| Calendrier | construit par le groupe | Jours fériés (`holidays`), vacances scolaires A, B, C (data.education.gouv.fr ; Bulletin officiel pour 2015-2017), ponts |

Tout se télécharge automatiquement : `python -m src.rte`, `python -m src.pipeline_meteo`,
`python -m src.calendrier`.

| Dossier | Contenu |
|---|---|
| `donnees-brutes/` | fichiers téléchargés, jamais modifiés |
| `interim/` | étapes intermédiaires de la consommation |
| `donnees-traitees/meteo/` | étapes de la météo : matrices, journaux, diagnostics, benchmarks |
| `donnees-preparees/` | fichiers finaux : `rte/`, `meteo/`, `calendrier/` |

## Constats sur les fichiers d'exemple de 2016

Ces constats portent sur les fichiers de 2016 uniquement. **À re-vérifier sur les
autres années**, surtout 2024 et 2025 (le format peut changer).

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
  27 mars (02:00 et 03:00 identiques). Ces jours sont à traiter à part.
- Le jeu en ligne `eco2mix-national-cons-def` a un format différent (date en UTC) :
  la source retenue pour le pipeline est à confirmer.

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
- Couverture 2016 des 8 stations retenues : de 2 861 à 2 927 observations sur 2 928 attendues
  (Strasbourg est la moins complète).
