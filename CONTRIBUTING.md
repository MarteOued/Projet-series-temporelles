# Règles de collaboration

## Répartition

| | Martino | Khadim | Les deux |
|---|---|---|---|
| Domaine | Consommation et modèles de référence | Météo, calendrier et modèle élaboré | Protocole et évaluation |
| Fichiers | `src/rte.py`, `src/benchmarks.py`, `src/modeles_lineaires.py` | `src/meteo.py`, `src/calendrier.py`, `src/modeles_ml.py` | `src/config.py`, `src/protocole.py`, `src/features.py`, `src/evaluation.py`, `docs/`, rapport, oral |

## Git

- Ne jamais travailler directement sur `main`.
- Une branche par personne et par sujet : `martino/rte`, `khadim/meteo`, `khadim/calendrier`...
- Le code réutilisable va dans `src/`. Les notebooks ne font que l'appeler.
- On fusionne dans `main` par une pull request **relue par l'autre**. On ne valide jamais sa propre pull request.
  Celui qui relit lance le code avant de valider.
- Avant de commiter un notebook : `Edit > Clear all outputs`.
- Pas de `git push --force` sur une branche partagée.
- Ne jamais commiter de mot de passe, de jeton ou de clé.
- Les données ne sont pas versionnées. Elles se retéléchargent avec les scripts ; le Drive partagé sert de sauvegarde
  et pour échanger les gros fichiers.

## Commandes

```bash
git checkout main && git pull           # repartir de la dernière version
git checkout -b khadim/meteo            # une branche par sujet
git status                              # vérifier ce qu'on va envoyer
git add src/meteo.py                    # ajouter les fichiers voulus
git commit -m "Message clair"
git push -u origin khadim/meteo         # puis ouvrir la pull request sur GitHub
git fetch && git merge origin/main      # récupérer le travail de l'autre sur sa branche
```

## Changer une décision

On modifie la valeur dans `src/config.py` **et** on ajoute une ligne à l'historique de `docs/decisions.md`
(sans effacer l'ancienne), dans la même pull request.

## Checklist avant chaque pull request

- [ ] Le code tourne depuis zéro (les données se retéléchargent).
- [ ] Aucune variable ne dépend d'une information postérieure à 14 h.
- [ ] Le test final (2024-2025) n'a pas été utilisé.
- [ ] `pytest` passe.
- [ ] `docs/decisions.md` est à jour.
- [ ] `docs/journal_ia.md` est à jour s'il y a eu un usage notable de l'IA.

## Notebooks

| Notebook | Responsable |
|---|---|
| `00_demarrage_colab` | tous |
| `01_exploration_rte_martino` | Martino |
| `01_meteo_calendrier_khadim` | Khadim (un seul notebook pour l'exploration météo et calendrier) |
| `02_preparation` | à deux (pull request relue par l'autre) |
| `03_benchmarks_martino` | Martino |
| `04_modele_simple_martino` | Martino |
| `04_modele_ml_khadim` | Khadim |
| `05_evaluation` | à deux (pull request relue par l'autre) |
