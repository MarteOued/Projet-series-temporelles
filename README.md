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
| Météo | SYNOP (Météo-France), 8 stations, observations toutes les 3 heures en UTC |
| Calendrier | construit par le groupe : jours fériés, vacances scolaires, ponts |

Les données ne sont pas dans le dépôt : elles se téléchargent dans `data/donnees-brutes/` avec les scripts. Formats et constats : `data/README.md`.

## Décisions

Toutes les décisions (période, découpage, heure de référence, stations, Covid, modèles) sont dans
`docs/decisions.md`, et leurs valeurs dans `src/config.py`. En résumé :

- apprentissage 2016-2022, validation 2023, test 2024-2025 (jours cibles) ;
- réestimation mensuelle, avec uniquement des données antérieures au jour prédit ;
- dernière consommation connue à 14 h : tranche 12 h-13 h ; météo : dernière observation avant 13 h locale ;
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
  meteo.py             météo : lecture, stations, température nationale        (à écrire)
  calendrier.py        variables calendaires                                    (à écrire)
  protocole.py         règle des 14 h (écrite) et découpage chronologique       (à écrire)
  features.py          variables construites à 14 h, sans fuite                 (à écrire)
  benchmarks.py        benchmarks sans apprentissage (B1, B2)
  modeles_lineaires.py régressions linéaires                                    (à écrire)
  modeles_ml.py        gradient boosting et météo parfaite                      (à écrire)
  evaluation.py        MAE, RMSE, MAPE, biais, total du jour, pointe, heure de pointe
tests/                 tests automatiques, dont le test de non-fuite
docs/                  décisions, protocole, disponibilité des variables, journal de l'IA
notebooks/             notebooks Colab (enveloppes autour de src/)
data/                  donnees-brutes/, interim/, donnees-preparees/ : non versionnés
report/                tables/ et figures/
```

## Installation

```bash
git clone https://github.com/MarteOued/Projet-series-temporelles.git
cd Projet-series-temporelles
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Ordre d'exécution

| # | Étape | Commande | Sortie | Coût | État |
|---|---|---|---|---|---|
| 1 | Tests | `pytest` | tous les tests passent (aucun appel réseau) | rapide | disponible |
| 2 | Consommation | `python -m src.rte` | `data/donnees-preparees/rte/conso_horaire_utc.csv` | **coûteux** : téléchargement de 85 Mo (une seule fois, mis en cache) | disponible. Explications : `notebooks/01_donnees_RTE.ipynb` |
| 3 | Météo | `python -m src.meteo` | `data/donnees-preparees/meteo_horaire_utc.csv` | **coûteux** : un fichier par année, mis en cache | à écrire |
| 4 | Calendrier | `python -m src.calendrier` | `data/donnees-preparees/calendrier.csv` | rapide | à écrire |
| 5 | Variables à 14 h et test de non-fuite | à définir | | | à écrire |
| 6 | Benchmarks | `python -m src.benchmarks` | scores B1 et B2 (apprentissage, validation) ; explications : `notebooks/03_benchmarks.ipynb` | rapide (quelques secondes) | disponible |
| 7 | Modèles, évaluation | à définir | tables et figures dans `report/` | **coûteux** : réestimation mensuelle | à écrire |

## Travailler à deux

Voir `CONTRIBUTING.md` : une branche par personne et par sujet, pull request relue par l'autre, jamais de travail direct sur `main`.

## État d'avancement

- [x] Compréhension du sujet
- [x] Décisions principales (`docs/decisions.md`)
- [x] Structure du dépôt
- [ ] Données propres reproduites depuis zéro : consommation **faite** ; météo et calendrier à faire
- [ ] Variables à 14 h et test de non-fuite
- [ ] Benchmarks et évaluation sur la validation 2023
- [ ] Modèles, ablation, test de sensibilité sur 2020
- [ ] Test final (une seule fois)
- [ ] Audit critique
- [ ] Rapport, README final, oral

## Usage de l'IA

Autorisé, mais chacun doit comprendre, vérifier et pouvoir expliquer tout le travail. Le journal est dans `docs/journal_ia.md`.
