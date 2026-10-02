# Prévision de la consommation électrique en France

Projet de séries temporelles : à 14h le jour J, prévoir la consommation horaire des 24 heures de J+1 (France métropolitaine).

Sources : éCO2mix (RTE) et observations SYNOP (Météo-France).

## Structure

- `data/raw/` : données brutes (non versionnées)
- `data/processed/` : données nettoyées (non versionnées)
- `src/` : code réutilisable (chargement, features, modèles, évaluation)
- `notebooks/` : exploration et expériences
- `report/` : mini-rapport (< 10 pages) et figures

## Reproduire

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

1. Placer les données dans `data/raw/` (voir `data/README.md`).
2. Lancer les notebooks dans l'ordre.

## Usage de l'IA

Documenter ici 3 exemples d'utilisation de l'IA (requis par le sujet).
