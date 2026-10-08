"""Compare les benchmarks (B0, B1, B2) et les modèles (M1 à M4) sur les MÊMES jours.

Le sujet demande de comparer toutes les méthodes sur les mêmes dates. Je réutilise donc
les mêmes outils que pour les benchmarks : src/benchmarks.py pour B0, B1, B2 et
src/evaluation.py (comparer) qui ne garde que les jours où TOUTES les méthodes ont
leurs 24 heures.

Utilisation
-----------
    python -m src.comparaison                 # validation 2023
    python -m src.comparaison --test-final    # + test 2024-2025 (choix déjà gelés)

Les prévisions des modèles sont lues dans data/resultats (écrites par src/experiences.py,
et par src/analyses.py pour le plafond « météo parfaite »).
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src import benchmarks, config, evaluation, rte

DOSSIER_RESULTATS = config.RACINE / "data" / "resultats"

MODELES = {
    "M1 : calendrier + retards": "m1",
    "M2 : M1 + température": "m2",
    "M3 : gradient boosting": "m3",
    "M4 : M1 + ARMA": "m4",
    # Pas une prévision possible à 14 h : la vraie température du jour cible (src/analyses.py)
    "Plafond : M2 + météo parfaite": "plafond",
}

FICHIERS_PREDICTIONS = {
    "validation": "predictions_validation_{}_2023.csv",
    "test": "predictions_test_final_{}_2024_2025.csv",
}


def tableau_jour_heure(predictions: pd.DataFrame, colonne: str = "prediction_MW") -> pd.DataFrame:
    """Passe d'une ligne par (jour, heure) à une ligne par jour et 24 colonnes (heures de Paris)."""
    tableau = predictions.assign(
        jour_cible=pd.to_datetime(predictions["jour_cible"])
    ).pivot(index="jour_cible", columns="heure_cible", values=colonne)
    tableau = tableau.reindex(columns=benchmarks.HEURES)
    tableau.index.name = None
    tableau.columns.name = "heure"
    return tableau


def lire_previsions_modeles(nom_periode: str) -> tuple[dict, dict]:
    """Prévisions des modèles (jour x heure) et vraies valeurs qu'ils ont utilisées."""
    previsions, cibles = {}, {}
    for nom, code in MODELES.items():
        chemin = DOSSIER_RESULTATS / FICHIERS_PREDICTIONS[nom_periode].format(code)
        if not chemin.exists():
            raise FileNotFoundError(
                f"{chemin} introuvable : lancer d'abord `python -m src.experiences` "
                "puis `python -m src.analyses`."
            )
        predictions = pd.read_csv(chemin)
        previsions[nom] = tableau_jour_heure(predictions)
        cibles[nom] = tableau_jour_heure(predictions, "consommation_cible_MW")
    return previsions, cibles


def comparer_periode(nom_periode: str, test_final: bool = False, conso_h=None):
    """Scores de B0, B1, B2, M1 à M4 sur les jours communs d'une période.

    Renvoie (scores, vraies valeurs, prévisions) comme benchmarks.evaluer_periode.
    """
    _, reel, previsions = benchmarks.evaluer_periode(nom_periode, conso_h, test_final=test_final)
    modeles, cibles = lire_previsions_modeles(nom_periode)

    # Contrôle : les modèles ont bien appris à prévoir la même consommation que celle notée ici
    for nom, cible in cibles.items():
        jours = cible.index.intersection(reel.index)
        ecart = np.nanmax(np.abs(cible.loc[jours].to_numpy() - reel.loc[jours].to_numpy()))
        if ecart > 1e-6:
            raise ValueError(f"{nom} : sa cible diffère de la consommation RTE ({ecart} MW).")

    previsions = {**previsions, **modeles}
    return evaluation.comparer(reel, previsions), reel, previsions


def scores_par_annee(reel, previsions) -> pd.DataFrame:
    """Mêmes scores, année par année, toujours sur les jours communs à toutes les méthodes."""
    jours = evaluation.jours_comparables(reel, *previsions.values())
    tableaux = []
    for annee in sorted(set(jours.year)):
        jours_annee = jours[jours.year == annee]
        scores = evaluation.comparer(
            reel.loc[jours_annee], {nom: p.loc[jours_annee] for nom, p in previsions.items()}
        )
        tableaux.append(scores.T.assign(annee=annee))
    return pd.concat(tableaux).rename_axis("methode").reset_index()


def _sauver(tableau: pd.DataFrame, nom: str) -> None:
    chemin = DOSSIER_RESULTATS / f"{nom}.csv"
    tableau.to_csv(chemin, index=False)
    print(f"  -> {chemin.relative_to(config.RACINE)}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test-final", action="store_true",
                        help="compare aussi sur le test 2024-2025 (choix déjà gelés)")
    args = parser.parse_args(argv)

    pd.set_option("display.width", 160)
    conso_h = rte.lire_prepare()
    periodes = [("validation", "comparaison_validation_2023")]
    if args.test_final:
        periodes.append(("test", "comparaison_test_2024_2025"))

    for nom_periode, fichier in periodes:
        scores, reel, previsions = comparer_periode(nom_periode, args.test_final, conso_h)
        print(f"\n=== {nom_periode} ===")
        print(scores.round(1).to_string())
        _sauver(scores.T.rename_axis("methode").reset_index(), fichier)
        if nom_periode == "test":
            _sauver(scores_par_annee(reel, previsions), fichier + "_par_annee")


if __name__ == "__main__":
    main()
