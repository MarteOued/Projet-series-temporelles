# Règles de collaboration

## Répartition
- **Martino** : RTE, cible, benchmarks, modèle simple (`src/rte.py`, `src/benchmarks.py`)
- **Binôme** : météo, calendrier, modèle ML (`src/meteo.py`, `src/calendrier.py`, `src/modeles_ml.py`)
- **Ensemble** : `src/protocole.py`, `src/evaluation.py`, évaluation, rapport, oral

## Git
- Ne jamais travailler directement sur `main`.
- Une branche par personne et par sujet : `martino/rte`, `binome/meteo`...
- Un notebook par personne et par étape, avec son prénom : `01_rte_exploration_martino.ipynb`.
- Le code réutilisable va dans `src/`, les notebooks ne font que l'appeler.
- On fusionne dans `main` via une pull request relue par l'autre.
- Avant de commiter un notebook : `Edit > Clear all outputs`.
- Les données ne sont pas versionnées : elles sont sur le Drive partagé.

## Commandes
```bash
git checkout -b martino/rte
git add -A && git commit -m "Message clair"
git push -u origin martino/rte
```

## Protocole (rappel)
À 14h le jour J, on prévoit les 24 heures de J+1. Aucune variable inconnue à 14h J ne doit être utilisée.

## Notebooks
| Notebook | Responsable |
|---|---|
| `00_demarrage_colab` | tous |
| `01_exploration_rte_martino` | Martino |
| `01_exploration_meteo_binome` | binôme |
| `02_preparation` | à deux (PR relue par l'autre) |
| `03_benchmarks_martino` | Martino |
| `04_modele_simple_martino` | Martino |
| `04_modele_ml_binome` | binôme |
| `05_evaluation` | à deux (PR relue par l'autre) |
