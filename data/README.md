# Données

Aucune donnée n'est versionnée (voir `.gitignore`). Les fichiers bruts vont dans
`data/donnees-brutes/`, les intermédiaires dans `data/interim/`, les fichiers propres dans
`data/donnees-preparees/`. Les scripts du dossier `src/` les téléchargent ou les produisent.

## Sources

| Donnée | Source | Remarque |
|---|---|---|
| Consommation | éCO2mix national (RTE), consommation en MW | Version définitive ou consolidée selon l'année : voir `docs/decisions.md` |
| Météo | SYNOP (Météo-France), observations toutes les 3 heures | Heures en UTC ; liste officielle des stations fournie à part |
| Calendrier | construit par le groupe | Jours fériés, vacances scolaires (zones A, B, C), ponts |

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
