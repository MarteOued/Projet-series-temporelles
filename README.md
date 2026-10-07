# Prévision de la consommation électrique en France métropolitaine

Projet de séries temporelles (Données temporelles, Université Lumière Lyon 2), travail en binôme, 50 % de la note.

- Auteurs : Khadim NGOM et Martine Ouedraogo
- Date de rendu : 11/10/2026 
- Dépôt : https://github.com/MarteOued/Projet-series-temporelles

## Objectif

Chaque jour J à 14 h (heure de Paris), prévoir les 24 valeurs horaires de consommation électrique du jour J+1.

**Règle centrale** : on n'utilise que l'information réellement disponible à 14 h le jour J. Utiliser autre chose est
une fuite d'information. Deux scénarios sont séparés :

- **opérationnel** : seulement l'information connue à 14 h (c'est le seul présenté comme déployable) ;
- **météo parfaite** : ajoute la météo observée de J+1, uniquement comme borne de comparaison.

Détail des règles : `docs/protocole.md`. Tableau de disponibilité des variables : `docs/disponibilite_variables.md`.

## Données

| Donnée | Source |
|---|---|
| Consommation | éCO2mix national (RTE), ramenée à l'heure |
| Météo | SYNOP (Météo-France) : 40 stations stables et métropolitaines pour nettoyer et imputer ; 38 stations continentales (sans la Corse) pour la température France, en 3 versions candidates à comparer sur 2023 |
| Calendrier | construit par le groupe : jours fériés, vacances scolaires, ponts |

Les données ne sont pas dans le dépôt : elles se téléchargent dans `data/donnees-brutes/` avec les scripts. Formats et constats : `data/README.md`.

## Décisions

Toutes les décisions (période, découpage, heure de référence, stations, Covid, modèles) sont dans
`docs/decisions.md`, et leurs valeurs dans `src/config.py`. En résumé :

- apprentissage 2016-2022, validation 2023, test 2024-2025 (jours cibles) ;
- réestimation mensuelle, avec uniquement des données antérieures au jour prédit ;
- dernière consommation connue à 14 h : tranche 12 h-13 h ; météo : dernière observation avant 13 h locale ;
- tout ce qui est appris sur les données (imputation météo, seuils, poids) l'est sur 2016-2022 seulement ;
- premier confinement de 2020 retiré de l'apprentissage seulement ;
- test final utilisé **une seule fois**, après gel écrit des choix.

## Organisation du dépôt

```text
README.md              ce fichier
CONTRIBUTING.md        façon de travailler à deux
requirements.txt       dépendances Python
pytest.ini             configuration des tests
src/
  config.py            décisions du groupe (valeurs)
  rte.py               consommation : téléchargement, passage à l'heure
  meteo.py             météo : téléchargements, lecture, choix des 40 stations
  pipeline_meteo.py    toute la météo en une commande (lance les modules ci-dessous)
    imputation_meteo.py, benchmark_imputation.py          imputation spatiale (voisins au même instant)
    diagnostic_trous_meteo.py                             trous restants (pannes du réseau)
    imputation_temporelle.py, benchmark_imputation_temporelle.py   imputation temporelle causale
    correction_anomalies_meteo.py, diagnostic_anomalies_meteo.py   règle d'anomalie et contrôle
    validation_meteo.py                                   contrôles de la matrice finale
    temperature_france.py                                 3 températures France candidates, horaires
  calendrier.py        variables calendaires (fériés, ponts, vacances, période de Noël candidate)
  vacances.py, recuperation_vacances*.py   calendriers scolaires
  protocole.py         règle des 14 h (conso, météo), bornes de l'apprentissage (découpage : config.py ; blocs : modeles_lineaires.py)
  features.py          table des variables connues à 14 h (dataset de modélisation)
  benchmarks.py        benchmarks sans apprentissage (B0, B1, B2)
  modeles_lineaires.py M1 : calendrier + consommation passée, un modèle par heure
  modeles_meteo.py     M2 : M1 + température (course des 3 températures, variantes)
  modeles_hgbr.py      M3 : gradient boosting
  modeles_arma.py      M4 : M1 + correction ARMA de ses erreurs ; evaluation_finale_m4.py
  experiences.py       refait tous les fichiers de data/resultats
  comparaison.py       benchmarks et modèles notés sur les mêmes jours
  analyses.py          plafond météo parfaite, décision 14, erreurs par groupe, pires jours
  test_bonus.py        test bonus janvier-juin 2026 (une seule fois)
  visualisation.py     fichiers lus par le tableau de bord
app/tableau_de_bord.py  tableau de bord Streamlit (visite guidée des résultats)
  evaluation.py        MAE, RMSE, MAPE, biais, total du jour, pointe, heure de pointe
tests/                 tests automatiques, dont le test de non-fuite
docs/                  décisions, protocole, disponibilité des variables, journal de l'IA
notebooks/             notebooks Colab (enveloppes autour de src/)
data/                  donnees-brutes/, interim/, donnees-traitees/, donnees-preparees/ : non versionnés
                       resultats/ : scores et prévisions des modèles (versionnés, refaits par experiences.py)
report/                tables/ et figures/
```

## Installation

```bash
git clone https://github.com/MarteOued/Projet-series-temporelles.git
cd Projet-series-temporelles
python -m venv .venv          # Python 3.13 (versions figées dans requirements.txt)
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Ordre d'exécution

| # | Étape | Commande | Sortie | Coût | État |
|---|---|---|---|---|---|
| 1 | Tests | `pytest` | aucun appel réseau. Les tests sur les vraies données (archives SYNOP, calendriers scolaires, résultats du pipeline) sont **ignorés** tant que les étapes 2 à 4 n'ont pas été lancées : relancer `pytest` après | rapide (quelques minutes avec toutes les données). Les tests de `tests/test_meteo.py` lisent de gros fichiers : sur un ordinateur avec peu de mémoire libre (moins de 4 Go), ils peuvent échouer par manque de mémoire dans la suite complète ; ils passent alors lancés seuls | disponible |
| 2 | Consommation | `python -m src.rte` | `data/donnees-preparees/rte/conso_horaire_utc.csv` | **coûteux** : téléchargement de 85 Mo (une seule fois, mis en cache) | disponible. Explications : `notebooks/01_donnees_RTE.ipynb` |
| 3 | Météo | `python -m src.pipeline_meteo` | `data/donnees-preparees/meteo/temperatures_france_candidates_horaire_utc.csv` (3 candidates, versions opérationnelle et météo parfaite) ; étapes et journaux dans `data/donnees-traitees/meteo/` | **coûteux** : téléchargement d'environ 80 Mo (une fois), puis environ 15 min (benchmark temporel). Option `--benchmark-spatial` : environ 5 min de plus | disponible |
| 4 | Calendrier | `python -m src.calendrier` | `data/donnees-preparees/calendrier/calendrier.csv` | rapide | disponible |
| 5 | Variables à 14 h | `python -m src.features` | `data/donnees-preparees/dataset_modelisation_2016_2025.csv` (87 192 lignes : une par jour cible et par heure, jours de changement d'heure exclus) | environ 2 min | disponible |
| 6 | Benchmarks | `python -m src.benchmarks` | scores B0, B1 et B2 (apprentissage, validation) ; explications : `notebooks/03_benchmarks.ipynb` | rapide (quelques secondes) | disponible |
| 7 | Choix sur la validation 2023 | `python -m src.experiences` | `data/resultats/` : ablations de M1 (retards, calendrier), course des températures et variantes de M2, grilles de M3 et M4 | **coûteux** : environ 15 min | disponible |
| 8 | Test final 2024-2025 | `python -m src.experiences --test-final` | `data/resultats/` : prévisions et scores des configurations **gelées** (reproduction, aucun choix n'en dépend) | **coûteux** : environ 30 min au total, réestimation mensuelle | disponible |
| 9 | Analyses | `python -m src.analyses` (2023) ; `--test-final` (+ 2024-2025) | `data/resultats/` : plafond « météo parfaite », décision 14 (un modèle contre 24), erreurs par saison, type de jour, température, heure et mois, 3 pires jours de M2 | quelques minutes | disponible |
| 10 | Comparaison sur les mêmes jours | `python -m src.comparaison` (2023) ; `--test-final` (+ 2024-2025) | `data/resultats/comparaison_*.csv` : B0, B1, B2, M1 à M4 et le plafond notés sur les jours où toutes les méthodes ont leurs 24 heures | rapide | disponible |
| 11 | Test bonus 2026 | `python -m src.test_bonus` | `data/resultats/test_bonus_2026_*.csv` et prévisions : janvier à juin 2026, configurations gelées, réestimation mensuelle, toutes les méthodes sur les mêmes jours. **Une seule fois** (décision 3) | environ 15 min | fait le 2026-10-07 |
| 12 | Fichiers du tableau de bord | `python -m src.visualisation` | `data/resultats/visualisation_previsions.csv` (toutes les prévisions, mêmes jours) et `visualisation_jours.csv` (un résumé par jour sur 10 ans) | rapide | disponible |

## Tableau de bord

Une visite guidée des résultats, écrite pour être comprise par tout le monde (pas seulement par des
spécialistes) : le problème en une image, les données, un jour au choix (réalité contre prévisions),
le classement des méthodes et ce qui est significatif, les erreurs par saison, type de jour,
température et heure, les pires journées expliquées, le biais, les choix faits sur 2023, les limites
et un lexique.

```bash
streamlit run app/tableau_de_bord.py
```

Il ne recalcule aucun modèle : il lit `data/resultats/` (versionné), il marche donc dès le clonage du
dépôt. Les scores sont calculés avec `src/evaluation.py` : ce sont les mêmes que dans le notebook 04.

## Notebooks

Les notebooks expliquent et illustrent ; le code est dans `src/`. Ils doivent tourner avec le Python
du projet (`.venv`), pas avec un autre Python installé sur la machine (Anaconda, par exemple) :

- dans VS Code : choisir le noyau `.venv` (en haut à droite du notebook) ;
- en ligne de commande : `python -m nbconvert --to notebook --execute --inplace notebooks/<nom>.ipynb`
  avec le Python du `.venv`. Éviter `python -m jupyter nbconvert`, qui peut lancer le Jupyter d'un
  autre Python trouvé dans le PATH.

| Notebook | Contenu |
|---|---|
| `01_donnees_RTE` | préparation de la consommation, disponibilité à 14 h |
| `02_relation_conso_meteo_calendrier` | relation consommation-température, effets calendaires (2016-2022) |
| `03_benchmarks` | benchmarks B0, B1, B2 et mesures d'erreur |
| `04_resultats_modeles` | tous les résultats : comparaison sur les mêmes jours, biais, ablations, décision 14, réglages de M3 et M4, erreurs par saison, type de jour, température et heure, 3 pires jours, stabilité, limites. Lit `data/resultats/` (aucun calcul de modèle) |
| `exploration_meteo` | réseau des 40 stations météo |
| `exploration_calendrier` | variables calendaires |

## Travailler à deux

Voir `CONTRIBUTING.md` : une branche par personne et par sujet, pull request relue par l'autre, jamais de travail direct sur `main`.

## État d'avancement

- [x] Compréhension du sujet
- [x] Décisions principales (`docs/decisions.md`)
- [x] Structure du dépôt
- [x] Données propres reproduites depuis zéro : consommation, météo (imputation causale), calendrier
- [x] Exploration : relation avec la météo, effets calendaires (notebook 02)
- [x] Benchmarks B0, B1, B2 (notebook 03)
- [x] Variables à 14 h et test de non-fuite (`src/features.py`, `tests/test_features.py`)
- [x] Choix sur la validation 2023 : température France, ablations, réglages de M3 et M4, décision 14, sensibilité au Covid
- [x] Test final 2024-2025 (chronologie de son utilisation écrite dans `docs/decisions.md`)
- [x] Comparaison sur les mêmes jours, plafond « météo parfaite », analyses par groupe, 3 pires jours (notebook 04)
- [x] Test bonus janvier-juin 2026, lancé une seule fois (`src/test_bonus.py`, notebook 04)
- [ ] Journal de l'IA : 3 exemples chacun (`docs/journal_ia.md`)
- [ ] Rapport (moins de 10 pages), oral (10 min)

## Usage de l'IA

Autorisé, mais chacun doit comprendre, vérifier et pouvoir expliquer tout le travail. Le journal est dans `docs/journal_ia.md`.
