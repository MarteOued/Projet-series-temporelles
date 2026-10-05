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
  protocole.py         règle des 14 h (conso, météo), fin de l'apprentissage ; découpage (à écrire)
  features.py          variables construites à 14 h, sans fuite                 (à écrire)
  benchmarks.py        benchmarks sans apprentissage (B0, B1, B2)
  modeles_lineaires.py régressions linéaires                                    (à écrire)
  modeles_ml.py        gradient boosting et météo parfaite                      (à écrire)
  evaluation.py        MAE, RMSE, MAPE, biais, total du jour, pointe, heure de pointe
tests/                 tests automatiques, dont le test de non-fuite
docs/                  décisions, protocole, disponibilité des variables, journal de l'IA
notebooks/             notebooks Colab (enveloppes autour de src/)
data/                  donnees-brutes/, interim/, donnees-traitees/, donnees-preparees/ : non versionnés
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
| 1 | Tests | `pytest` | aucun appel réseau. Les tests sur les vraies données (archives SYNOP, calendriers scolaires, résultats du pipeline) sont **ignorés** tant que les étapes 2 à 4 n'ont pas été lancées : relancer `pytest` après | rapide (quelques minutes avec toutes les données) | disponible |
| 2 | Consommation | `python -m src.rte` | `data/donnees-preparees/rte/conso_horaire_utc.csv` | **coûteux** : téléchargement de 85 Mo (une seule fois, mis en cache) | disponible. Explications : `notebooks/01_donnees_RTE.ipynb` |
| 3 | Météo | `python -m src.pipeline_meteo` | `data/donnees-preparees/meteo/temperatures_france_candidates_horaire_utc.csv` (3 candidates, versions opérationnelle et météo parfaite) ; étapes et journaux dans `data/donnees-traitees/meteo/` | **coûteux** : téléchargement d'environ 80 Mo (une fois), puis environ 15 min (benchmark temporel). Option `--benchmark-spatial` : environ 5 min de plus | disponible |
| 4 | Calendrier | `python -m src.calendrier` | `data/donnees-preparees/calendrier/calendrier.csv` | rapide | disponible |
| 5 | Variables à 14 h et test de non-fuite | à définir | | | à écrire |
| 6 | Benchmarks | `python -m src.benchmarks` | scores B0, B1 et B2 (apprentissage, validation) ; explications : `notebooks/03_benchmarks.ipynb` | rapide (quelques secondes) | disponible |
| 7 | Modèles, évaluation | à définir | tables et figures dans `report/` | **coûteux** : réestimation mensuelle | à écrire |

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
| `exploration_meteo` | réseau des 40 stations météo |
| `exploration_calendrier` | variables calendaires |

## Travailler à deux

Voir `CONTRIBUTING.md` : une branche par personne et par sujet, pull request relue par l'autre, jamais de travail direct sur `main`.

## État d'avancement

- [x] Compréhension du sujet
- [x] Décisions principales (`docs/decisions.md`)
- [x] Structure du dépôt
- [x] Données propres reproduites depuis zéro : consommation, météo (imputation causale), calendrier
- [ ] Choix de la température France sur 2023 (3 candidates prêtes)
- [ ] Variables à 14 h et test de non-fuite
- [ ] Benchmarks et évaluation sur la validation 2023
- [ ] Modèles, ablation, test de sensibilité sur 2020
- [ ] Test final (une seule fois)
- [ ] Audit critique
- [ ] Rapport, README final, oral

## Usage de l'IA

Autorisé, mais chacun doit comprendre, vérifier et pouvoir expliquer tout le travail. Le journal est dans `docs/journal_ia.md`.
