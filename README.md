# Prévision de la consommation électrique en France métropolitaine

Projet de séries temporelles (Données temporelles, Université Lumière Lyon 2), travail en binôme, 50 % de la note.

- Auteurs : Khadim NGOM et Martino [NOM À COMPLÉTER]
- Date de rendu : [À COMPLÉTER] · Date de l'oral : [À COMPLÉTER]
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

Les données ne sont pas dans le dépôt : elles se téléchargent dans `data/raw/` avec les scripts. Formats et constats : `data/README.md`.

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
  rte.py               consommation : téléchargement, passage à l'heure         (à écrire)
  meteo.py             météo : lecture, stations, température nationale        (à écrire)
  calendrier.py        variables calendaires                                    (à écrire)
  protocole.py         règle des 14 h et découpage chronologique                (à écrire)
  features.py          variables construites à 14 h, sans fuite                 (à écrire)
  benchmarks.py        benchmarks sans apprentissage                            (à écrire)
  modeles_lineaires.py régressions linéaires                                    (à écrire)
  modeles_ml.py        gradient boosting et météo parfaite                      (à écrire)
  evaluation.py        MAE, RMSE, total du jour, pointe, heure de pointe        (à écrire)
tests/                 tests automatiques, dont le test de non-fuite
docs/                  décisions, protocole, disponibilité des variables, journal de l'IA
notebooks/             notebooks Colab (enveloppes autour de src/)
data/                  raw/, interim/, processed/ : non versionnés
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
| 2 | Consommation | `python -m src.rte` | `data/processed/conso_horaire_utc.csv` | **coûteux** : téléchargement | à écrire |
| 3 | Météo | `python -m src.meteo` | `data/processed/meteo_horaire_utc.csv` | **coûteux** : un fichier par année, mis en cache | à écrire |
| 4 | Calendrier | `python -m src.calendrier` | `data/processed/calendrier.csv` | rapide | à écrire |
| 5 | Variables à 14 h et test de non-fuite | à définir | | | à écrire |
| 6 | Benchmarks, modèles, évaluation | à définir | tables et figures dans `report/` | **coûteux** : réestimation mensuelle | à écrire |

## Travailler à deux

Voir `CONTRIBUTING.md` : une branche par personne et par sujet, pull request relue par l'autre, jamais de travail direct sur `main`.

## État d'avancement

- [x] Compréhension du sujet
- [x] Décisions principales (`docs/decisions.md`)
- [x] Structure du dépôt
- [ ] Données propres reproduites depuis zéro (consommation, météo, calendrier)
- [ ] Variables à 14 h et test de non-fuite
- [ ] Benchmarks et évaluation sur la validation 2023
- [ ] Modèles, ablation, test de sensibilité sur 2020
- [ ] Test final (une seule fois)
- [ ] Audit critique
- [ ] Rapport, README final, oral

## Usage de l'IA

Autorisé, mais chacun doit comprendre, vérifier et pouvoir expliquer tout le travail. Le journal est dans `docs/journal_ia.md`.
