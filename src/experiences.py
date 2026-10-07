"""Refait tous les fichiers de data/resultats à partir du dataset de modélisation.

Utilisation
-----------
    python -m src.features                    # construit le dataset (une fois)
    python -m src.experiences                 # choix sur la validation 2023
    python -m src.experiences --test-final    # + reproduction du test 2024-2025

Deux parties bien séparées
--------------------------
1. Validation 2023 (sélection) : ablations de M1 (retards, calendrier),
   course des 3 températures et variantes météo de M2, grille de M3,
   grille de M4. Tous les choix du projet viennent de ces fichiers.

2. Test final 2024-2025 : il REPRODUIT les résultats des configurations
   déjà gelées (M1, M2, M3, M4). Il ne sert à choisir aucun réglage :
   c'est pourquoi il ne se lance qu'avec l'option --test-final.
"""

from __future__ import annotations

import argparse
import contextlib
from unittest import mock

import pandas as pd

from src import config, features
from src import evaluation_finale_m4 as e4
from src import modeles_arma as m4
from src import modeles_hgbr as m3
from src import modeles_lineaires as m1
from src import modeles_meteo as m2

DOSSIER_RESULTATS = config.RACINE / "data" / "resultats"

COLONNES_METRIQUES = [
    "MAE_MW",
    "RMSE_MW",
    "MAE_total_journalier_MWh",
    "MAE_pointe_MW",
    "MAE_heure_pointe_h",
    "nb_jours_complets",
]


# ===========================================================================
# Variantes de M1 pour les ablations
# ===========================================================================

def _retards(*, veille: bool, lag48: bool):
    """Fabrique une règle « heure -> retards » ; le retard 168 h est toujours là."""

    def variables_retards(heure: int) -> list[str]:
        m1.verifier_heure(heure)
        retards = []
        # La veille effective (24 h) n'est connue à 14 h que pour H <= 12.
        if veille and heure <= config.DERNIERE_HEURE_CONSO_CONNUE:
            retards.append("conso_veille_effective_MW")
        if lag48:
            retards.append("conso_lag48_MW")
        retards.append("conso_lag168_MW")
        return retards

    return variables_retards


VARIANTES_RETARDS = {
    "LAG-A": _retards(veille=True, lag48=False),
    "LAG-B": _retards(veille=True, lag48=True),     # retenue dans M1
    "LAG-C": _retards(veille=False, lag48=True),
    "LAG-D": _retards(veille=False, lag48=False),
}

_FERIES = ["ferie", "veille_ferie", "lendemain_ferie", "pont_potentiel"]
_VACANCES = ["vacances_A", "vacances_B", "vacances_C"]

VARIANTES_CALENDRIER = {
    "CAL-A": ["ferie"],
    "CAL-B": _FERIES,
    "CAL-C": _FERIES + ["nb_zones_vacances"],
    "CAL-D": _FERIES + _VACANCES,                   # retenue dans M1
    "CAL-E": _FERIES + _VACANCES + ["periode_noel"],
    "CAL-F": _FERIES + ["nb_zones_vacances", "periode_noel"],
}


@contextlib.contextmanager
def variante_m1(retards=None, calendrier=None):
    """Remplace, le temps d'un calcul, les retards ou le calendrier utilisés par M1.

    En dehors du bloc ``with``, M1 retrouve sa définition retenue (LAG-B, CAL-D).
    """
    with contextlib.ExitStack() as pile:
        if retards is not None:
            pile.enter_context(
                mock.patch.object(m1, "variables_retards_m1", retards)
            )
        if calendrier is not None:
            pile.enter_context(
                mock.patch.object(
                    m1, "VARIABLES_CALENDRIER_BINAIRES_M1", list(calendrier)
                )
            )
        yield


# ===========================================================================
# Petits outils de mise en forme
# ===========================================================================

def _erreurs_par_groupe(predictions: pd.DataFrame, groupe) -> pd.DataFrame:
    """MAE et RMSE par groupe (trimestre, heure...)."""
    erreur = predictions[m1.COLONNE_CIBLE] - predictions["prediction_MW"]
    tableau = pd.DataFrame({
        "groupe": groupe,
        "abs": erreur.abs(),
        "carre": erreur ** 2,
    }).groupby("groupe", sort=True)
    return pd.DataFrame({
        "n_predictions": tableau.size(),
        "MAE_MW": tableau["abs"].mean(),
        "RMSE_MW": tableau["carre"].mean() ** 0.5,
    })


def _par_trimestre(predictions: pd.DataFrame) -> pd.DataFrame:
    return (
        _erreurs_par_groupe(predictions, predictions["bloc_validation"])
        .rename_axis("bloc_validation")
        .reset_index()
    )


def _ligne_metriques(resultat_metriques: dict, n_predictions: int) -> dict:
    ligne = {"n_predictions": n_predictions}
    ligne.update({cle: resultat_metriques[cle] for cle in COLONNES_METRIQUES})
    return ligne


def _sauver_predictions_validation(predictions: pd.DataFrame, modele: str) -> None:
    """Prévisions 2023 de la configuration retenue (pour la comparaison aux benchmarks)."""
    colonnes = [m1.COLONNE_JOUR, m1.COLONNE_HEURE, m1.COLONNE_CIBLE, "prediction_MW", "bloc_validation"]
    _sauver(predictions[colonnes], f"predictions_validation_{modele}_2023")


def _sauver(tableau: pd.DataFrame, nom: str) -> None:
    chemin = DOSSIER_RESULTATS / f"{nom}.csv"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tableau.to_csv(chemin, index=False)
    print(f"  -> {chemin.relative_to(config.RACINE)}")


# ===========================================================================
# 1. Validation 2023 : sélection
# ===========================================================================

def ablation_retards_m1(donnees: pd.DataFrame) -> None:
    print("Ablation des retards de M1 (2023)")
    lignes, trimestres, groupes = [], [], []

    for nom, retards in VARIANTES_RETARDS.items():
        with variante_m1(retards=retards):
            resultat = m1.valider_m1_expanding(donnees)
        p = resultat.predictions

        lignes.append({"variante": nom, **_ligne_metriques(resultat.metriques, len(p))})
        trimestres.append(_par_trimestre(p).assign(variante=nom))

        groupe = p[m1.COLONNE_HEURE].le(config.DERNIERE_HEURE_CONSO_CONNUE).map(
            {True: "H<=12", False: "H>12"}
        )
        groupes.append(
            _erreurs_par_groupe(p, groupe)
            .rename_axis("groupe_heures").reset_index().assign(variante=nom)
        )

    _sauver(pd.DataFrame(lignes).sort_values("MAE_MW"), "ablation_lags_m1_2023")
    _sauver(
        pd.concat(trimestres)[["variante", "bloc_validation", "n_predictions", "MAE_MW", "RMSE_MW"]],
        "ablation_lags_m1_2023_par_trimestre",
    )
    _sauver(
        pd.concat(groupes)[["variante", "groupe_heures", "n_predictions", "MAE_MW", "RMSE_MW"]],
        "ablation_lags_m1_2023_par_groupe_heures",
    )


def ablation_calendrier_m1(donnees: pd.DataFrame) -> None:
    print("Ablation du calendrier de M1 (2023)")
    lignes, trimestres = [], []

    for nom, variables in VARIANTES_CALENDRIER.items():
        with variante_m1(calendrier=variables):
            resultat = m1.valider_m1_expanding(donnees)
        p = resultat.predictions

        lignes.append({
            "variante": nom,
            "variables": " + ".join(variables),
            **_ligne_metriques(resultat.metriques, len(p)),
        })
        trimestres.append(_par_trimestre(p).assign(variante=nom))

    _sauver(pd.DataFrame(lignes).sort_values("MAE_MW"), "ablation_calendrier_m1_2023")
    _sauver(
        pd.concat(trimestres)[["variante", "bloc_validation", "n_predictions", "MAE_MW", "RMSE_MW"]],
        "ablation_calendrier_m1_2023_par_trimestre",
    )


def ablation_m2(donnees: pd.DataFrame) -> None:
    print("Course des 3 températures et variantes météo de M2 (2023)")
    ablation = m2.comparer_ablations_m2(donnees)

    # Gain de chaque variante par rapport à M1 (positif = M2 fait mieux)
    validation_m1 = m1.valider_m1_expanding(donnees)
    _sauver_predictions_validation(validation_m1.predictions, "m1")
    reference = validation_m1.metriques
    tableau = ablation.tableau.copy()
    for mesure in ("MAE", "RMSE"):
        gain = reference[f"{mesure}_MW"] - tableau[f"{mesure}_MW"]
        tableau[f"gain_{mesure}_vs_M1_MW"] = gain
        tableau[f"gain_{mesure}_vs_M1_pct"] = 100 * gain / reference[f"{mesure}_MW"]
    _sauver(
        tableau[[c for c in tableau.columns if not c.startswith("gain_")]
                + ["gain_MAE_vs_M1_MW", "gain_MAE_vs_M1_pct",
                   "gain_RMSE_vs_M1_MW", "gain_RMSE_vs_M1_pct"]],
        "ablation_m2_2023",
    )

    # Configuration retenue = la meilleure MAE 2023 (première ligne du tableau)
    meilleure = tableau.sort_values("MAE_MW").iloc[0]
    retenue = ablation.resultats[(meilleure["candidat_temperature"], meilleure["variante_meteo"])]
    _sauver_predictions_validation(retenue.predictions, "m2")

    trimestres, heures = [], []
    for (candidat, variante), resultat in ablation.resultats.items():
        p = resultat.predictions
        cles = {"candidat_temperature": candidat, "variante_meteo": variante}
        trimestres.append(_par_trimestre(p).assign(**cles))
        heures.append(
            _erreurs_par_groupe(p, p[m2.COLONNE_HEURE])
            .rename_axis("heure_cible").reset_index().assign(**cles)
        )

    debut = ["candidat_temperature", "variante_meteo"]
    _sauver(
        pd.concat(trimestres)[debut + ["bloc_validation", "n_predictions", "MAE_MW", "RMSE_MW"]],
        "ablation_m2_2023_par_trimestre",
    )
    _sauver(
        pd.concat(heures)[debut + ["heure_cible", "n_predictions", "MAE_MW", "RMSE_MW"]],
        "ablation_m2_2023_par_heure",
    )


GRILLE_M3 = {
    "M3-1": dict(learning_rate=0.05, max_iter=300, max_leaf_nodes=15, l2_regularization=1.0),
    "M3-2": dict(learning_rate=0.05, max_iter=300, max_leaf_nodes=31, l2_regularization=1.0),
    "M3-3": dict(learning_rate=0.05, max_iter=300, max_leaf_nodes=63, l2_regularization=1.0),
    "M3-4": dict(learning_rate=0.10, max_iter=200, max_leaf_nodes=31, l2_regularization=1.0),
}


def selection_m3(donnees: pd.DataFrame) -> None:
    print("Grille de M3 (2023)")
    lignes, predictions = [], {}
    for nom, parametres in GRILLE_M3.items():
        print(f"  {nom} ...")
        resultat = m3.valider_m3_expanding(donnees, **parametres)
        predictions[nom] = resultat.predictions
        lignes.append({
            "configuration": nom,
            **parametres,
            **{cle: resultat.metriques[cle] for cle in COLONNES_METRIQUES[:-1]},
        })
    tableau = pd.DataFrame(lignes).sort_values("MAE_MW")
    _sauver(tableau, "selection_m3_validation_2023")
    _sauver_predictions_validation(predictions[tableau["configuration"].iloc[0]], "m3")


def selection_m4(donnees: pd.DataFrame) -> None:
    print("Grille de M4 (2023)")
    lignes, predictions = [], {}
    for nom, (p, q) in m4.GRILLE_M4.items():
        print(f"  {nom} ...")
        resultat = m4.valider_m4_expanding(donnees, nom)
        predictions[nom] = resultat.predictions
        lignes.append({
            "configuration": nom,
            "p": p,
            "q": q,
            **{cle: resultat.metriques[cle] for cle in COLONNES_METRIQUES[:-1]},
            "nb_observations": len(resultat.predictions),
        })
    tableau = pd.DataFrame(lignes).sort_values("MAE_MW")
    _sauver(tableau, "selection_m4_validation_2023")
    _sauver_predictions_validation(predictions[tableau["configuration"].iloc[0]], "m4")


# ===========================================================================
# 2. Test final 2024-2025 : reproduction des configurations gelées
# ===========================================================================

def _metriques_test(predictions: pd.DataFrame) -> pd.DataFrame:
    """Métriques finales pour 2024, 2025, puis les deux années ensemble."""
    par_annee = e4.calculer_metriques_par_annee(predictions)
    par_annee["periode"] = par_annee.pop("annee").astype(int).astype(str)
    ensemble = pd.DataFrame([{
        "periode": "2024-2025",
        **m1.calculer_metriques_finales(predictions),
    }])
    tableau = pd.concat([par_annee, ensemble], ignore_index=True)
    return tableau[["periode"] + [c for c in tableau.columns if c != "periode"]]


def test_final(donnees: pd.DataFrame) -> None:
    print("Test final 2024-2025 (configurations gelées)")

    print("  M1 et M2 ...")
    r1 = m1.evaluer_m1_test_final(donnees)
    r2 = m2.evaluer_m2_test_final(donnees, "temp_38_ponderee", "M2-F")
    _sauver(r1.predictions, "predictions_test_final_m1_2024_2025")
    _sauver(r2.predictions, "predictions_test_final_m2_2024_2025")
    m1_m2 = pd.concat([
        _metriques_test(r.predictions).assign(modele=nom)
        for nom, r in (("M1", r1), ("M2", r2))
    ])
    m1_m2 = m1_m2.loc[m1_m2["periode"] != "2024-2025"].rename(columns={"periode": "annee"})
    _sauver(
        m1_m2[["modele"] + [c for c in m1_m2.columns if c != "modele"]],
        "test_final_m1_m2_2024_2025",
    )

    print("  M3 ...")
    r3 = m3.evaluer_m3_test_final(donnees)
    _sauver(r3.predictions, "predictions_test_final_m3_2024_2025")
    m3_tableau = _metriques_test(r3.predictions).assign(modele=r3.configuration)
    _sauver(
        m3_tableau[["modele"] + [c for c in m3_tableau.columns if c != "modele"]],
        "test_final_m3_2024_2025",
    )

    print("  M4 ...")
    e4.sauvegarder_resultats(e4.evaluer_m4_test_final(donnees))


# ===========================================================================
# Lancement
# ===========================================================================

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--test-final",
        action="store_true",
        help="reproduit aussi le test 2024-2025 des configurations gelées",
    )
    args = parser.parse_args(argv)

    if not features.FICHIER_DATASET.exists():
        raise FileNotFoundError(
            f"{features.FICHIER_DATASET} introuvable : lancer d'abord `python -m src.features`."
        )
    donnees = pd.read_csv(features.FICHIER_DATASET)

    ablation_retards_m1(donnees)
    ablation_calendrier_m1(donnees)
    ablation_m2(donnees)
    selection_m3(donnees)
    selection_m4(donnees)

    if args.test_final:
        test_final(donnees)


if __name__ == "__main__":
    main()
