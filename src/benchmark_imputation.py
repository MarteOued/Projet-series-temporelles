"""Benchmark des méthodes d'imputation des températures SYNOP.

Objectif
--------
Comparer différentes méthodes permettant de reconstruire les températures
manquantes des 40 stations SYNOP stables de France métropolitaine.

Benchmark A
-----------
Masquage aléatoire de 5 % des températures réellement observées.

Méthodes comparées
------------------
1. Valeur de la station la plus corrélée.
2. Régression linéaire sur la station la plus corrélée.
3. Régression linéaire multiple sur les 3 stations les plus corrélées.
4. Régression multi-voisins adaptative :
   - 3 voisins disponibles -> modèle à 3 voisins ;
   - 2 voisins disponibles -> modèle à 2 voisins ;
   - 1 voisin disponible   -> modèle à 1 voisin ;
   - aucun voisin          -> pas de prédiction.

Important
---------
La matrice originale n'est jamais utilisée pour entraîner les modèles après
la création du benchmark. Les températures artificiellement cachées restent
donc inconnues des méthodes d'imputation.
"""

from itertools import combinations

import numpy as np
import pandas as pd

from src.meteo import (
    lire_archive_synop,
    stations_stables_metropolitaines,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

ANNEE_DEBUT = 2015
ANNEE_FIN = 2025

DEBUT = pd.Timestamp(
    "2015-12-01 00:00:00",
    tz="UTC",
)

FIN = pd.Timestamp(
    "2025-12-31 21:00:00",
    tz="UTC",
)

GRAINE = 42
TAUX_MASQUAGE = 0.05

NB_VOISINS = 3
MIN_OBSERVATIONS_REGRESSION = 1000


# =============================================================================
# CONSTRUCTION DE LA MATRICE DES TEMPERATURES
# =============================================================================

def construire_matrice_temperatures():
    """Construit la matrice timestamp x station en degrés Celsius."""

    stations = stations_stables_metropolitaines()

    codes = (
        stations["geo_id_wmo"]
        .astype(str)
        .str.zfill(5)
        .tolist()
    )

    morceaux = []

    for annee in range(
        ANNEE_DEBUT,
        ANNEE_FIN + 1,
    ):
        print(f"Lecture : {annee}")

        d = lire_archive_synop(annee)

        d["geo_id_wmo"] = (
            d["geo_id_wmo"]
            .astype(str)
            .str.zfill(5)
        )

        d = d[
            d["geo_id_wmo"].isin(codes)
        ][
            [
                "validity_time",
                "geo_id_wmo",
                "t",
            ]
        ].copy()

        morceaux.append(d)

    meteo = pd.concat(
        morceaux,
        ignore_index=True,
    )

    meteo = meteo[
        (meteo["validity_time"] >= DEBUT)
        & (meteo["validity_time"] <= FIN)
    ].copy()

    meteo["temperature_c"] = (
        meteo["t"] - 273.15
    )

    matrice = meteo.pivot_table(
        index="validity_time",
        columns="geo_id_wmo",
        values="temperature_c",
        aggfunc="mean",
    )

    grille_complete = pd.date_range(
        start=DEBUT,
        end=FIN,
        freq="3h",
        inclusive="both",
    )

    matrice = matrice.reindex(
        index=grille_complete,
        columns=codes,
    ).sort_index()

    matrice.index.name = "validity_time"

    return matrice, stations


# =============================================================================
# BENCHMARK A
# =============================================================================

def creer_benchmark_aleatoire(
    matrice,
    taux=TAUX_MASQUAGE,
    graine=GRAINE,
):
    """Masque aléatoirement une partie des températures observées."""

    rng = np.random.default_rng(graine)

    positions_observees = np.argwhere(
        matrice.notna().to_numpy()
    )

    nb_observations = len(
        positions_observees
    )

    nb_a_masquer = int(
        taux * nb_observations
    )

    indices_tires = rng.choice(
        nb_observations,
        size=nb_a_masquer,
        replace=False,
    )

    positions_masquees = (
        positions_observees[
            indices_tires
        ]
    )

    matrice_benchmark = matrice.copy()

    verite = []

    for ligne, colonne in positions_masquees:

        timestamp = matrice.index[ligne]
        station = matrice.columns[colonne]

        temperature = matrice.iat[
            ligne,
            colonne,
        ]

        verite.append(
            {
                "timestamp": timestamp,
                "station": station,
                "temperature_reelle": temperature,
            }
        )

        matrice_benchmark.iat[
            ligne,
            colonne,
        ] = np.nan

    verite = pd.DataFrame(verite)

    return matrice_benchmark, verite


# =============================================================================
# CORRELATIONS ENTRE STATIONS
# =============================================================================

def calculer_correlations(
    matrice_benchmark,
):
    """Calcule la matrice de corrélation entre stations."""

    return matrice_benchmark.corr(
        method="pearson",
        min_periods=1000,
    )


def stations_plus_correlees(
    correlations,
):
    """Retourne le meilleur voisin de chaque station."""

    voisins = {}

    for station in correlations.columns:

        serie = (
            correlations[station]
            .drop(index=station)
            .dropna()
            .sort_values(
                ascending=False
            )
        )

        if not serie.empty:
            voisins[station] = (
                serie.index[0]
            )

    return voisins


def k_stations_plus_correlees(
    correlations,
    k=NB_VOISINS,
):
    """Retourne les k meilleurs voisins de chaque station."""

    voisins = {}

    for station in correlations.columns:

        serie = (
            correlations[station]
            .drop(index=station)
            .dropna()
            .sort_values(
                ascending=False
            )
        )

        voisins[station] = (
            serie
            .head(k)
            .index
            .tolist()
        )

    return voisins


# =============================================================================
# OUTIL GENERAL DE REGRESSION
# =============================================================================

def ajuster_regression(
    matrice_benchmark,
    station,
    voisins,
):
    """Ajuste une régression linéaire avec les voisins indiqués."""

    colonnes = [
        station,
        *voisins,
    ]

    donnees = (
        matrice_benchmark[
            colonnes
        ]
        .dropna()
    )

    if (
        len(donnees)
        < MIN_OBSERVATIONS_REGRESSION
    ):
        return None

    y = (
        donnees[station]
        .to_numpy(
            dtype=float
        )
    )

    X = (
        donnees[voisins]
        .to_numpy(
            dtype=float
        )
    )

    X_design = np.column_stack(
        [
            np.ones(len(X)),
            X,
        ]
    )

    coefficients, _, _, _ = (
        np.linalg.lstsq(
            X_design,
            y,
            rcond=None,
        )
    )

    return {
        "voisins": list(voisins),
        "intercept": float(
            coefficients[0]
        ),
        "coefficients": (
            coefficients[1:]
            .astype(float)
        ),
        "n_apprentissage": len(
            donnees
        ),
    }


# =============================================================================
# METHODE 1
# =============================================================================

def predire_voisin_correle(
    matrice_benchmark,
    verite,
    voisins,
):
    """Prédit avec la température du meilleur voisin."""

    resultats = verite.copy()

    resultats[
        "station_voisine"
    ] = resultats[
        "station"
    ].map(voisins)

    predictions = []

    for ligne in resultats.itertuples():

        timestamp = ligne.timestamp
        voisin = ligne.station_voisine

        if (
            pd.isna(voisin)
            or voisin
            not in matrice_benchmark.columns
        ):
            predictions.append(
                np.nan
            )
            continue

        prediction = (
            matrice_benchmark.at[
                timestamp,
                voisin,
            ]
        )

        predictions.append(
            prediction
        )

    resultats[
        "temperature_predite"
    ] = predictions

    return resultats


# =============================================================================
# METHODE 2
# =============================================================================

def ajuster_regressions_voisins(
    matrice_benchmark,
    voisins,
):
    """Ajuste une régression sur le meilleur voisin de chaque station."""

    modeles = {}

    for station, voisin in voisins.items():

        modele = ajuster_regression(
            matrice_benchmark,
            station,
            [voisin],
        )

        if modele is not None:
            modeles[station] = modele

    return modeles


def predire_regression_voisin(
    matrice_benchmark,
    verite,
    modeles,
):
    """Prédit avec la régression sur le meilleur voisin."""

    resultats = verite.copy()

    stations_voisines = []
    predictions = []

    for ligne in resultats.itertuples():

        station = ligne.station
        timestamp = ligne.timestamp

        modele = modeles.get(
            station
        )

        if modele is None:
            stations_voisines.append(
                np.nan
            )
            predictions.append(
                np.nan
            )
            continue

        voisin = (
            modele["voisins"][0]
        )

        stations_voisines.append(
            voisin
        )

        temperature_voisin = (
            matrice_benchmark.at[
                timestamp,
                voisin,
            ]
        )

        if pd.isna(
            temperature_voisin
        ):
            predictions.append(
                np.nan
            )
            continue

        prediction = (
            modele["intercept"]
            + modele["coefficients"][0]
            * temperature_voisin
        )

        predictions.append(
            float(prediction)
        )

    resultats[
        "station_voisine"
    ] = stations_voisines

    resultats[
        "temperature_predite"
    ] = predictions

    return resultats


# =============================================================================
# METHODE 3
# =============================================================================

def ajuster_regressions_multi_voisins(
    matrice_benchmark,
    voisins_multi,
):
    """Ajuste une régression utilisant simultanément les 3 meilleurs voisins."""

    modeles = {}

    for station, voisins in voisins_multi.items():

        if len(voisins) < NB_VOISINS:
            continue

        modele = ajuster_regression(
            matrice_benchmark,
            station,
            voisins,
        )

        if modele is not None:
            modeles[station] = modele

    return modeles


def predire_regression_multi_voisins(
    matrice_benchmark,
    verite,
    modeles,
):
    """Prédit uniquement lorsque les 3 voisins sont disponibles."""

    resultats = verite.copy()

    predictions = []
    voisins_utilises = []

    for ligne in resultats.itertuples():

        station = ligne.station
        timestamp = ligne.timestamp

        modele = modeles.get(
            station
        )

        if modele is None:
            predictions.append(
                np.nan
            )
            voisins_utilises.append(
                ""
            )
            continue

        voisins = modele[
            "voisins"
        ]

        temperatures = (
            matrice_benchmark.loc[
                timestamp,
                voisins,
            ]
        )

        voisins_utilises.append(
            ",".join(voisins)
        )

        if temperatures.isna().any():
            predictions.append(
                np.nan
            )
            continue

        x = temperatures.to_numpy(
            dtype=float
        )

        prediction = (
            modele["intercept"]
            + np.dot(
                modele["coefficients"],
                x,
            )
        )

        predictions.append(
            float(prediction)
        )

    resultats[
        "voisins_utilises"
    ] = voisins_utilises

    resultats[
        "temperature_predite"
    ] = predictions

    return resultats


# =============================================================================
# METHODE 3 ADAPTATIVE
# =============================================================================

def ajuster_modeles_adaptatifs(
    matrice_benchmark,
    voisins_multi,
):
    """Ajuste tous les sous-modèles possibles parmi les 3 voisins."""

    modeles_adaptatifs = {}

    for station, voisins in voisins_multi.items():

        modeles_station = {}

        nb_voisins = len(
            voisins
        )

        for taille in range(
            nb_voisins,
            0,
            -1,
        ):

            for combinaison in combinations(
                voisins,
                taille,
            ):

                combinaison = tuple(
                    combinaison
                )

                modele = ajuster_regression(
                    matrice_benchmark,
                    station,
                    list(combinaison),
                )

                if modele is not None:
                    modeles_station[
                        combinaison
                    ] = modele

        if modeles_station:
            modeles_adaptatifs[
                station
            ] = modeles_station

    return modeles_adaptatifs


def predire_regression_adaptative(
    matrice_benchmark,
    verite,
    modeles_adaptatifs,
):
    """Prédit avec le sous-modèle utilisant le maximum de voisins disponibles."""

    resultats = verite.copy()

    predictions = []
    voisins_utilises = []
    nombres_voisins = []

    for ligne in resultats.itertuples():

        station = ligne.station
        timestamp = ligne.timestamp

        modeles_station = (
            modeles_adaptatifs.get(
                station
            )
        )

        if not modeles_station:
            predictions.append(
                np.nan
            )
            voisins_utilises.append(
                ""
            )
            nombres_voisins.append(
                0
            )
            continue

        modele_choisi = None
        combinaison_choisie = None

        for combinaison, modele in (
            modeles_station.items()
        ):

            temperatures = (
                matrice_benchmark.loc[
                    timestamp,
                    list(combinaison),
                ]
            )

            if temperatures.notna().all():
                modele_choisi = modele
                combinaison_choisie = (
                    combinaison
                )
                break

        if modele_choisi is None:
            predictions.append(
                np.nan
            )
            voisins_utilises.append(
                ""
            )
            nombres_voisins.append(
                0
            )
            continue

        temperatures = (
            matrice_benchmark.loc[
                timestamp,
                list(
                    combinaison_choisie
                ),
            ]
            .to_numpy(
                dtype=float
            )
        )

        prediction = (
            modele_choisi[
                "intercept"
            ]
            + np.dot(
                modele_choisi[
                    "coefficients"
                ],
                temperatures,
            )
        )

        predictions.append(
            float(prediction)
        )

        voisins_utilises.append(
            ",".join(
                combinaison_choisie
            )
        )

        nombres_voisins.append(
            len(
                combinaison_choisie
            )
        )

    resultats[
        "voisins_utilises"
    ] = voisins_utilises

    resultats[
        "nombre_voisins"
    ] = nombres_voisins

    resultats[
        "temperature_predite"
    ] = predictions

    return resultats


# =============================================================================
# EVALUATION
# =============================================================================

def evaluer_predictions(
    resultats,
):
    """Calcule couverture, MAE et RMSE."""

    evaluables = resultats[
        resultats[
            "temperature_predite"
        ].notna()
    ].copy()

    evaluables["erreur"] = (
        evaluables[
            "temperature_predite"
        ]
        - evaluables[
            "temperature_reelle"
        ]
    )

    couverture = (
        100
        * len(evaluables)
        / len(resultats)
    )

    mae = (
        evaluables[
            "erreur"
        ]
        .abs()
        .mean()
    )

    rmse = np.sqrt(
        np.mean(
            evaluables["erreur"]
            ** 2
        )
    )

    return {
        "n_total": len(
            resultats
        ),
        "n_predites": len(
            evaluables
        ),
        "couverture_pct": couverture,
        "mae": mae,
        "rmse": rmse,
    }


def afficher_scores(
    titre,
    scores,
):
    """Affiche les scores d'une méthode."""

    print()
    print("=" * 90)
    print(titre)
    print("=" * 90)

    print(
        "Valeurs à prédire :",
        scores["n_total"],
    )

    print(
        "Valeurs prédites :",
        scores["n_predites"],
    )

    print(
        "Couverture :",
        f"{scores['couverture_pct']:.3f} %",
    )

    print(
        "MAE :",
        f"{scores['mae']:.4f} °C",
    )

    print(
        "RMSE :",
        f"{scores['rmse']:.4f} °C",
    )


# =============================================================================
# COMPARAISON SUR UN MEME SOUS-ENSEMBLE
# =============================================================================

def comparer_sur_intersection(
    verite,
    resultats_methodes,
):
    """Compare les méthodes sur les observations prédites par toutes."""

    comparaison = verite[
        [
            "timestamp",
            "station",
            "temperature_reelle",
        ]
    ].copy()

    colonnes_predictions = []

    for nom, resultats in (
        resultats_methodes.items()
    ):

        colonne = (
            f"prediction_{nom}"
        )

        comparaison[
            colonne
        ] = resultats[
            "temperature_predite"
        ].to_numpy()

        colonnes_predictions.append(
            colonne
        )

    commun = comparaison.dropna(
        subset=colonnes_predictions
    ).copy()

    lignes = []

    for nom in resultats_methodes:

        colonne = (
            f"prediction_{nom}"
        )

        erreur = (
            commun[colonne]
            - commun[
                "temperature_reelle"
            ]
        )

        lignes.append(
            {
                "methode": nom,
                "n_commun": len(
                    commun
                ),
                "MAE_commune": (
                    erreur.abs().mean()
                ),
                "RMSE_commun": np.sqrt(
                    np.mean(
                        erreur ** 2
                    )
                ),
            }
        )

    return pd.DataFrame(
        lignes
    )


# =============================================================================
# DIAGNOSTIC DE LA METHODE ADAPTATIVE
# =============================================================================

def analyser_methode_adaptative(
    resultats,
):
    """Analyse les performances selon le nombre de voisins utilisés.

    Pour chaque nombre de voisins :
    - effectif ;
    - proportion ;
    - MAE ;
    - RMSE ;
    - biais moyen.

    Les cas avec 0 voisin correspondent aux valeurs non prédites.
    """

    donnees = resultats.copy()

    donnees["erreur"] = (
        donnees[
            "temperature_predite"
        ]
        - donnees[
            "temperature_reelle"
        ]
    )

    lignes = []

    for nb_voisins in [
        3,
        2,
        1,
        0,
    ]:

        sous_ensemble = donnees[
            donnees[
                "nombre_voisins"
            ] == nb_voisins
        ].copy()

        n = len(
            sous_ensemble
        )

        proportion = (
            100
            * n
            / len(donnees)
            if len(donnees) > 0
            else np.nan
        )

        evaluables = sous_ensemble[
            sous_ensemble[
                "temperature_predite"
            ].notna()
        ].copy()

        if len(evaluables) > 0:

            erreurs = (
                evaluables[
                    "erreur"
                ]
            )

            mae = (
                erreurs
                .abs()
                .mean()
            )

            rmse = np.sqrt(
                np.mean(
                    erreurs ** 2
                )
            )

            biais = (
                erreurs.mean()
            )

        else:

            mae = np.nan
            rmse = np.nan
            biais = np.nan

        lignes.append(
            {
                "nombre_voisins":
                    nb_voisins,
                "n":
                    n,
                "proportion_pct":
                    proportion,
                "MAE":
                    mae,
                "RMSE":
                    rmse,
                "biais":
                    biais,
            }
        )

    return pd.DataFrame(
        lignes
    )


# =============================================================================
# EXECUTION
# =============================================================================

def main():

    print("=" * 90)
    print(
        "BENCHMARK D'IMPUTATION SYNOP"
    )
    print("=" * 90)

    # =========================================================================
    # MATRICE
    # =========================================================================

    print()
    print(
        "Construction de la matrice..."
    )

    matrice, stations = (
        construire_matrice_temperatures()
    )

    nb_manquantes = int(
        matrice.isna()
        .sum()
        .sum()
    )

    print()
    print(
        "Dimensions :",
        matrice.shape,
    )

    print(
        "Valeurs manquantes réelles :",
        nb_manquantes,
    )

    assert matrice.shape == (
        29472,
        40,
    )

    assert nb_manquantes == 11285

    # =========================================================================
    # BENCHMARK
    # =========================================================================

    print()
    print(
        "Création du benchmark A..."
    )

    matrice_benchmark, verite = (
        creer_benchmark_aleatoire(
            matrice
        )
    )

    print(
        "Températures cachées :",
        len(verite),
    )

    assert len(verite) == 58379

    # =========================================================================
    # CORRELATIONS
    # =========================================================================

    print()
    print(
        "Calcul des corrélations..."
    )

    correlations = (
        calculer_correlations(
            matrice_benchmark
        )
    )

    voisins = (
        stations_plus_correlees(
            correlations
        )
    )

    voisins_multi = (
        k_stations_plus_correlees(
            correlations,
            k=NB_VOISINS,
        )
    )

    noms = (
        stations
        .assign(
            geo_id_wmo=lambda x:
                x["geo_id_wmo"]
                .astype(str)
                .str.zfill(5)
        )
        .set_index(
            "geo_id_wmo"
        )["name"]
        .to_dict()
    )

    print()
    print("=" * 90)
    print(
        "3 STATIONS LES PLUS "
        "CORRELEES - EXEMPLES"
    )
    print("=" * 90)

    for station in list(
        voisins_multi
    )[:10]:

        print()
        print(
            f"{station} - "
            f"{noms.get(station, station)}"
        )

        for rang, voisin in enumerate(
            voisins_multi[station],
            start=1,
        ):

            r = correlations.at[
                station,
                voisin,
            ]

            print(
                f"    {rang}. "
                f"{voisin} - "
                f"{noms.get(voisin, voisin)} "
                f"(r = {r:.4f})"
            )

    # =========================================================================
    # METHODE 1
    # =========================================================================

    print()
    print(
        "Méthode 1 : "
        "station la plus corrélée..."
    )

    resultats_baseline = (
        predire_voisin_correle(
            matrice_benchmark,
            verite,
            voisins,
        )
    )

    scores_baseline = (
        evaluer_predictions(
            resultats_baseline
        )
    )

    afficher_scores(
        "RESULTATS - METHODE 1 : "
        "STATION LA PLUS CORRELEE",
        scores_baseline,
    )

    # =========================================================================
    # METHODE 2
    # =========================================================================

    print()
    print(
        "Méthode 2 : "
        "régression sur le meilleur voisin..."
    )

    modeles_regression = (
        ajuster_regressions_voisins(
            matrice_benchmark,
            voisins,
        )
    )

    resultats_regression = (
        predire_regression_voisin(
            matrice_benchmark,
            verite,
            modeles_regression,
        )
    )

    scores_regression = (
        evaluer_predictions(
            resultats_regression
        )
    )

    afficher_scores(
        "RESULTATS - METHODE 2 : "
        "REGRESSION SUR LE MEILLEUR VOISIN",
        scores_regression,
    )

    # =========================================================================
    # METHODE 3
    # =========================================================================

    print()
    print(
        "Méthode 3 : "
        "régression sur 3 voisins..."
    )

    modeles_multi = (
        ajuster_regressions_multi_voisins(
            matrice_benchmark,
            voisins_multi,
        )
    )

    resultats_multi = (
        predire_regression_multi_voisins(
            matrice_benchmark,
            verite,
            modeles_multi,
        )
    )

    scores_multi = (
        evaluer_predictions(
            resultats_multi
        )
    )

    afficher_scores(
        "RESULTATS - METHODE 3 : "
        "REGRESSION MULTIPLE 3 VOISINS",
        scores_multi,
    )

    # =========================================================================
    # METHODE ADAPTATIVE
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "METHODE 3 ADAPTATIVE"
    )
    print("=" * 90)

    print()
    print(
        "Ajustement de tous les "
        "sous-modèles..."
    )

    modeles_adaptatifs = (
        ajuster_modeles_adaptatifs(
            matrice_benchmark,
            voisins_multi,
        )
    )

    print(
        "Stations avec modèles :",
        len(modeles_adaptatifs),
    )

    nb_modeles_total = sum(
        len(modeles)
        for modeles
        in modeles_adaptatifs.values()
    )

    print(
        "Nombre total de sous-modèles :",
        nb_modeles_total,
    )

    print()
    print(
        "Prédiction adaptative..."
    )

    resultats_adaptatifs = (
        predire_regression_adaptative(
            matrice_benchmark,
            verite,
            modeles_adaptatifs,
        )
    )

    scores_adaptatifs = (
        evaluer_predictions(
            resultats_adaptatifs
        )
    )

    afficher_scores(
        "RESULTATS - "
        "METHODE 3 ADAPTATIVE",
        scores_adaptatifs,
    )

    # =========================================================================
    # REPARTITION DU NOMBRE DE VOISINS
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "NOMBRE DE VOISINS UTILISES "
        "PAR LA METHODE ADAPTATIVE"
    )
    print("=" * 90)

    repartition = (
        resultats_adaptatifs[
            "nombre_voisins"
        ]
        .value_counts()
        .sort_index(
            ascending=False
        )
    )

    for nb, effectif in (
        repartition.items()
    ):

        pourcentage = (
            100
            * effectif
            / len(
                resultats_adaptatifs
            )
        )

        print(
            f"{nb} voisin(s) : "
            f"{effectif} "
            f"({pourcentage:.3f} %)"
        )

    # =========================================================================
    # DIAGNOSTIC PAR NOMBRE DE VOISINS
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "PERFORMANCE SELON LE NOMBRE "
        "DE VOISINS UTILISES"
    )
    print("=" * 90)

    diagnostic_adaptatif = (
        analyser_methode_adaptative(
            resultats_adaptatifs
        )
    )

    print(
        diagnostic_adaptatif.to_string(
            index=False,
            formatters={
                "proportion_pct":
                    lambda x: f"{x:.3f}",
                "MAE":
                    lambda x: (
                        f"{x:.4f}"
                        if pd.notna(x)
                        else "-"
                    ),
                "RMSE":
                    lambda x: (
                        f"{x:.4f}"
                        if pd.notna(x)
                        else "-"
                    ),
                "biais":
                    lambda x: (
                        f"{x:+.4f}"
                        if pd.notna(x)
                        else "-"
                    ),
            },
        )
    )

    assert (
        diagnostic_adaptatif[
            "n"
        ].sum()
        == len(
            resultats_adaptatifs
        )
    )

    print()
    print(
        "Contrôle :",
        diagnostic_adaptatif[
            "n"
        ].sum(),
        "cas analysés sur",
        len(
            resultats_adaptatifs
        ),
    )

    # =========================================================================
    # COMPARAISON GENERALE
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "COMPARAISON GENERALE"
    )
    print("=" * 90)

    comparaison = pd.DataFrame(
        [
            {
                "methode":
                    "Voisin corrélé brut",
                "couverture_pct":
                    scores_baseline[
                        "couverture_pct"
                    ],
                "MAE":
                    scores_baseline[
                        "mae"
                    ],
                "RMSE":
                    scores_baseline[
                        "rmse"
                    ],
            },
            {
                "methode":
                    "Régression 1 voisin",
                "couverture_pct":
                    scores_regression[
                        "couverture_pct"
                    ],
                "MAE":
                    scores_regression[
                        "mae"
                    ],
                "RMSE":
                    scores_regression[
                        "rmse"
                    ],
            },
            {
                "methode":
                    "Régression 3 voisins",
                "couverture_pct":
                    scores_multi[
                        "couverture_pct"
                    ],
                "MAE":
                    scores_multi[
                        "mae"
                    ],
                "RMSE":
                    scores_multi[
                        "rmse"
                    ],
            },
            {
                "methode":
                    "Régression adaptative",
                "couverture_pct":
                    scores_adaptatifs[
                        "couverture_pct"
                    ],
                "MAE":
                    scores_adaptatifs[
                        "mae"
                    ],
                "RMSE":
                    scores_adaptatifs[
                        "rmse"
                    ],
            },
        ]
    )

    print(
        comparaison.to_string(
            index=False,
            formatters={
                "couverture_pct":
                    lambda x: f"{x:.3f}",
                "MAE":
                    lambda x: f"{x:.4f}",
                "RMSE":
                    lambda x: f"{x:.4f}",
            },
        )
    )

    # =========================================================================
    # COMPARAISON SUR LES MEMES OBSERVATIONS
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "COMPARAISON SUR LES MEMES "
        "OBSERVATIONS"
    )
    print("=" * 90)

    comparaison_commune = (
        comparer_sur_intersection(
            verite,
            {
                "M1":
                    resultats_baseline,
                "M2":
                    resultats_regression,
                "M3":
                    resultats_multi,
                "M3_adapt":
                    resultats_adaptatifs,
            },
        )
    )

    print(
        comparaison_commune.to_string(
            index=False,
            formatters={
                "MAE_commune":
                    lambda x: f"{x:.4f}",
                "RMSE_commun":
                    lambda x: f"{x:.4f}",
            },
        )
    )

    # =========================================================================
    # BILAN
    # =========================================================================

    amelioration_mae_vs_m2 = (
        100
        * (
            scores_regression[
                "mae"
            ]
            - scores_adaptatifs[
                "mae"
            ]
        )
        / scores_regression[
            "mae"
        ]
    )

    amelioration_rmse_vs_m2 = (
        100
        * (
            scores_regression[
                "rmse"
            ]
            - scores_adaptatifs[
                "rmse"
            ]
        )
        / scores_regression[
            "rmse"
        ]
    )

    gain_couverture_vs_m3 = (
        scores_adaptatifs[
            "couverture_pct"
        ]
        - scores_multi[
            "couverture_pct"
        ]
    )

    print()
    print("=" * 90)
    print(
        "BILAN DE LA METHODE ADAPTATIVE"
    )
    print("=" * 90)

    print()
    print(
        "Amélioration MAE "
        "par rapport à M2 :",
        f"{amelioration_mae_vs_m2:.2f} %",
    )

    print(
        "Amélioration RMSE "
        "par rapport à M2 :",
        f"{amelioration_rmse_vs_m2:.2f} %",
    )

    print(
        "Gain de couverture "
        "par rapport à M3 :",
        f"{gain_couverture_vs_m3:.3f} "
        "points",
    )

    # =========================================================================
    # EXEMPLES
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "15 EXEMPLES DE PREDICTIONS "
        "ADAPTATIVES"
    )
    print("=" * 90)

    print(
        resultats_adaptatifs[
            [
                "timestamp",
                "station",
                "voisins_utilises",
                "nombre_voisins",
                "temperature_reelle",
                "temperature_predite",
            ]
        ]
        .head(15)
        .to_string(
            index=False
        )
    )


# =============================================================================
# LANCEMENT
# =============================================================================

if __name__ == "__main__":
    main()