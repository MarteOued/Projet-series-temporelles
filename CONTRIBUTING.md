# Règles de collaboration

## Répartition

| | Martino | Khadim | Les deux |
|---|---|---|---|
| Domaine | Consommation et modèles de référence | Météo, calendrier et modèle élaboré | Protocole et évaluation |
| Fichiers | `src/rte.py`, `src/benchmarks.py`, `src/evaluation.py`, `src/comparaison.py`, `src/analyses.py` | chaîne météo (`src/meteo.py` ... `src/temperature_france.py`), `src/calendrier.py`, `src/modeles_lineaires.py`, `src/modeles_meteo.py`, `src/modeles_hgbr.py`, `src/modeles_arma.py` | `src/config.py`, `src/protocole.py`, `src/features.py`, `src/experiences.py`, `docs/`, rapport, oral |

## Git

- Ne jamais travailler directement sur `main`.
- Une branche par personne et par sujet : `martino/rte`, `khadim/meteo`, `khadim/calendrier`...
- Le code réutilisable va dans `src/`. Les notebooks ne font que l'appeler.
- On fusionne dans `main` par une pull request **relue par l'autre**. On ne valide jamais sa propre pull request.
  Celui qui relit lance le code avant de valider.
- Un notebook est commité **avec ses sorties**, après l'avoir relancé en entier avec le Python du projet
  (`.venv/Scripts/python -m nbconvert --to notebook --execute --inplace notebooks/<nom>.ipynb`) : le
  correcteur voit ainsi les résultats sans relancer les calculs. Les commentaires sont relus face aux sorties.
- Pas de `git push --force` sur une branche partagée.
- Ne jamais commiter de mot de passe, de jeton ou de clé.
- Les données ne sont pas versionnées. Elles se retéléchargent avec les scripts ; le Drive partagé sert de sauvegarde
  et pour échanger les gros fichiers. Exception : `data/resultats/` (scores et prévisions des modèles) est versionné,
  et chaque fichier doit être produit par une commande du dépôt (`src/experiences.py`, `src/analyses.py`,
  `src/comparaison.py`), jamais à la main ni depuis un notebook.

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
- [ ] Le test final (2024-2025) n'a pas été utilisé pour choisir ou régler quoi que ce soit
  (seulement reproduit avec `--test-final`, ou relancé pour corriger une erreur notée dans `docs/decisions.md`).
- [ ] `pytest` passe.
- [ ] `docs/decisions.md` est à jour.
- [ ] `docs/journal_ia.md` est à jour s'il y a eu un usage notable de l'IA.

## Notebooks

| Notebook | Responsable |
|---|---|
| `01_donnees_RTE` | Martino |
| `02_relation_conso_meteo_calendrier` | Martino |
| `03_benchmarks` | Martino |
| `04_resultats_modeles` | à deux (pull request relue par l'autre) |
| `exploration_meteo` | Khadim |
| `exploration_calendrier` | Khadim |
