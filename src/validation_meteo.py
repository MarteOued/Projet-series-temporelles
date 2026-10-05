"""
Validation finale de la matrice des températures SYNOP.

Ce script contrôle la matrice finale obtenue après :
    1. imputation spatiale ;
    2. imputation temporelle ;
    3. correction des anomalies détectées par la règle.

Il ne modifie aucune donnée.

Contrôles réalisés :
    - dimensions ;
    - valeurs manquantes ;
    - doublons temporels ;
    - régularité de la grille temporelle ;
    - statistiques descriptives ;
    - températures extrêmes ;
    - variations temporelles importantes ;
    - statistiques par station ;
    - statistiques par année.

Exécution :
    python -m src.validation_meteo
"""

from pathlib import Path

import numpy as np
import pandas as pd
from src import config


# =============================================================================
# CONFIGURATION
# =============================================================================


DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

FICHIER_TEMPERATURES = (
    DOSSIER_METEO
    / "temperatures_synop_finales.csv"
)

FICHIER_STATS_STATIONS = (
    DOSSIER_METEO
    / "statistiques_temperatures_par_station.csv"
)

FICHIER_STATS_ANNEES = (
    DOSSIER_METEO
    / "statistiques_temperatures_par_annee.csv"
)

FICHIER_EXTREMES = (
    DOSSIER_METEO
    / "temperatures_extremes.csv"
)

FICHIER_VARIATIONS = (
    DOSSIER_METEO
    / "variations_temperatures_importantes.csv"
)


# Seuils uniquement utilisés pour le diagnostic.
# Les observations ne sont jamais supprimées automatiquement.
TEMP_MIN_CONTROLE = -30.0
TEMP_MAX_CONTROLE = 45.0

# Variation absolue entre deux observations espacées de 3 h.
DELTA_TEMP_CONTROLE = 15.0


# =============================================================================
# OUTILS
# =============================================================================

def titre(texte):
    print()
    print("=" * 90)
    print(texte)
    print("=" * 90)


def charger_matrice():
    """
    Charge la matrice finale des températures.
    """

    if not FICHIER_TEMPERATURES.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {FICHIER_TEMPERATURES}"
        )

    df = pd.read_csv(
        FICHIER_TEMPERATURES,
        index_col=0,
        parse_dates=True,
    )

    # Conversion explicite de l'index.
    df.index = pd.to_datetime(
        df.index,
        utc=True,
        errors="raise",
    )

    df.index.name = "timestamp"

    # Les identifiants WMO doivent rester des chaînes.
    df.columns = [
        str(col).zfill(5)
        for col in df.columns
    ]

    # Sécurité : toutes les températures doivent être numériques.
    df = df.apply(
        pd.to_numeric,
        errors="coerce",
    )

    return df


# =============================================================================
# CONTROLES GENERAUX
# =============================================================================

def controles_generaux(df):

    titre("CONTROLES GENERAUX")

    print("Dimensions :", df.shape)
    print("Nombre de timestamps :", len(df))
    print("Nombre de stations :", df.shape[1])

    print(
        "Première date :",
        df.index.min(),
    )

    print(
        "Dernière date :",
        df.index.max(),
    )

    nb_total = df.size

    nb_nan = int(
        df.isna().sum().sum()
    )

    print()
    print("Nombre total de valeurs :", nb_total)
    print("Valeurs manquantes :", nb_nan)

    if nb_nan == 0:
        print("Contrôle valeurs manquantes : OK")
    else:
        print("ATTENTION : valeurs manquantes détectées.")

    # -------------------------------------------------------------------------
    # Doublons temporels
    # -------------------------------------------------------------------------

    nb_doublons = int(
        df.index.duplicated().sum()
    )

    print()
    print("Timestamps dupliqués :", nb_doublons)

    if nb_doublons == 0:
        print("Contrôle doublons : OK")
    else:
        print("ATTENTION : timestamps dupliqués détectés.")

    # -------------------------------------------------------------------------
    # Ordre chronologique
    # -------------------------------------------------------------------------

    print()
    print(
        "Index trié chronologiquement :",
        df.index.is_monotonic_increasing,
    )


# =============================================================================
# REGULARITE TEMPORELLE
# =============================================================================

def controle_grille_temporelle(df):

    titre("REGULARITE DE LA GRILLE TEMPORELLE")

    differences = (
        df.index
        .to_series()
        .diff()
        .dropna()
    )

    distribution = (
        differences
        .value_counts()
        .sort_index()
    )

    print("Distribution des écarts entre timestamps :")
    print()

    for delta, n in distribution.items():
        print(
            f"{str(delta):>20} : {n}"
        )

    pas_attendu = pd.Timedelta(hours=3)

    nb_anormaux = int(
        (differences != pas_attendu).sum()
    )

    print()
    print(
        "Écarts différents de 3 h :",
        nb_anormaux,
    )

    if nb_anormaux == 0:
        print("Grille temporelle régulière : OK")
    else:
        print(
            "ATTENTION : la grille contient "
            "des écarts différents de 3 h."
        )


# =============================================================================
# STATISTIQUES GLOBALES
# =============================================================================

def statistiques_globales(df):

    titre("STATISTIQUES GLOBALES DES TEMPERATURES")

    valeurs = df.to_numpy().ravel()

    valeurs = valeurs[
        ~np.isnan(valeurs)
    ]

    serie = pd.Series(
        valeurs,
        name="temperature",
    )

    print(
        serie.describe(
            percentiles=[
                0.01,
                0.05,
                0.25,
                0.50,
                0.75,
                0.95,
                0.99,
            ]
        )
    )

    print()
    print(
        "Température minimale :",
        round(float(serie.min()), 3),
        "°C",
    )

    print(
        "Température maximale :",
        round(float(serie.max()), 3),
        "°C",
    )

    print(
        "Température moyenne :",
        round(float(serie.mean()), 3),
        "°C",
    )

    print(
        "Écart-type :",
        round(float(serie.std()), 3),
        "°C",
    )


# =============================================================================
# EXTREMES
# =============================================================================

def analyser_extremes(df):

    titre("CONTROLE DES TEMPERATURES EXTREMES")

    format_long = (
        df
        .stack()
        .rename("temperature")
        .reset_index()
    )

    format_long.columns = [
        "timestamp",
        "station",
        "temperature",
    ]

    extremes = format_long[
        (format_long["temperature"] < TEMP_MIN_CONTROLE)
        |
        (format_long["temperature"] > TEMP_MAX_CONTROLE)
    ].copy()

    extremes = extremes.sort_values(
        "temperature"
    )

    print(
        f"Seuil inférieur de contrôle : "
        f"{TEMP_MIN_CONTROLE} °C"
    )

    print(
        f"Seuil supérieur de contrôle : "
        f"{TEMP_MAX_CONTROLE} °C"
    )

    print()
    print(
        "Nombre de valeurs signalées :",
        len(extremes),
    )

    if extremes.empty:

        print(
            "Aucune température au-delà "
            "des seuils de contrôle."
        )

    else:

        print()
        print("Valeurs les plus basses :")
        print(
            extremes
            .head(20)
            .to_string(index=False)
        )

        print()
        print("Valeurs les plus hautes :")
        print(
            extremes
            .tail(20)
            .sort_values(
                "temperature",
                ascending=False,
            )
            .to_string(index=False)
        )

    extremes.to_csv(
        FICHIER_EXTREMES,
        index=False,
    )

    return extremes


# =============================================================================
# STATISTIQUES PAR STATION
# =============================================================================

def statistiques_par_station(df):

    titre("STATISTIQUES PAR STATION")

    stats = pd.DataFrame(
        {
            "n": df.count(),
            "moyenne": df.mean(),
            "ecart_type": df.std(),
            "minimum": df.min(),
            "q01": df.quantile(0.01),
            "q05": df.quantile(0.05),
            "mediane": df.median(),
            "q95": df.quantile(0.95),
            "q99": df.quantile(0.99),
            "maximum": df.max(),
        }
    )

    stats.index.name = "station"

    print(
        stats.round(3).to_string()
    )

    stats.to_csv(
        FICHIER_STATS_STATIONS
    )

    return stats


# =============================================================================
# STATISTIQUES PAR ANNEE
# =============================================================================

def statistiques_par_annee(df):

    titre("STATISTIQUES PAR ANNEE")

    format_long = (
        df
        .stack()
        .rename("temperature")
        .reset_index()
    )

    format_long.columns = [
        "timestamp",
        "station",
        "temperature",
    ]

    format_long["annee"] = (
        format_long["timestamp"].dt.year
    )

    stats = (
        format_long
        .groupby("annee")["temperature"]
        .agg(
            n="count",
            moyenne="mean",
            ecart_type="std",
            minimum="min",
            maximum="max",
        )
    )

    print(
        stats.round(3).to_string()
    )

    stats.to_csv(
        FICHIER_STATS_ANNEES
    )

    return stats


# =============================================================================
# VARIATIONS TEMPORELLES
# =============================================================================

def analyser_variations(df):

    titre("VARIATIONS TEMPORELLES IMPORTANTES")

    delta = df.diff()

    delta_abs = delta.abs()

    masque = (
        delta_abs
        > DELTA_TEMP_CONTROLE
    )

    positions = np.where(
        masque.to_numpy()
    )

    lignes = []

    for i, j in zip(
        positions[0],
        positions[1],
    ):

        timestamp = df.index[i]
        station = df.columns[j]

        temperature = df.iloc[i, j]

        temperature_precedente = (
            df.iloc[i - 1, j]
            if i > 0
            else np.nan
        )

        variation = delta.iloc[i, j]

        lignes.append(
            {
                "timestamp": timestamp,
                "station": station,
                "temperature_precedente":
                    temperature_precedente,
                "temperature":
                    temperature,
                "variation":
                    variation,
                "variation_absolue":
                    abs(variation),
            }
        )

    variations = pd.DataFrame(lignes)

    if not variations.empty:

        variations = (
            variations
            .sort_values(
                "variation_absolue",
                ascending=False,
            )
            .reset_index(drop=True)
        )

    print(
        "Seuil de contrôle :",
        DELTA_TEMP_CONTROLE,
        "°C en 3 h",
    )

    print(
        "Nombre de variations signalées :",
        len(variations),
    )

    if not variations.empty:

        print()
        print(
            "20 variations les plus importantes :"
        )

        print(
            variations
            .head(20)
            .to_string(index=False)
        )

    variations.to_csv(
        FICHIER_VARIATIONS,
        index=False,
    )

    return variations


# =============================================================================
# EXTREMES PAR STATION
# =============================================================================

def extremes_par_station(df):

    titre("STATIONS AUX TEMPERATURES LES PLUS EXTREMES")

    minima = df.min().sort_values()

    maxima = (
        df.max()
        .sort_values(
            ascending=False
        )
    )

    print("10 minima les plus bas :")
    print()

    for station, valeur in minima.head(10).items():
        print(
            f"{station} : "
            f"{valeur:.3f} °C"
        )

    print()
    print("10 maxima les plus élevés :")
    print()

    for station, valeur in maxima.head(10).items():
        print(
            f"{station} : "
            f"{valeur:.3f} °C"
        )


# =============================================================================
# CONTROLE FINAL
# =============================================================================

def controle_final(df):

    titre("CONTROLE FINAL")

    erreurs = []

    if df.isna().any().any():
        erreurs.append(
            "La matrice contient encore des NaN."
        )

    if df.index.duplicated().any():
        erreurs.append(
            "La matrice contient des timestamps dupliqués."
        )

    if not df.index.is_monotonic_increasing:
        erreurs.append(
            "L'index temporel n'est pas trié."
        )

    differences = (
        df.index
        .to_series()
        .diff()
        .dropna()
    )

    if (
        differences
        != pd.Timedelta(hours=3)
    ).any():

        erreurs.append(
            "La grille temporelle n'est pas "
            "strictement régulière à 3 h."
        )

    if len(erreurs) == 0:

        print("Tous les contrôles structurels sont validés.")
        print()
        print("Matrice météo finale : OK")

    else:

        print("ATTENTION :")

        for erreur in erreurs:
            print(" -", erreur)


# =============================================================================
# MAIN
# =============================================================================

def main():

    titre(
        "VALIDATION FINALE DE LA MATRICE METEO SYNOP"
    )

    print()
    print("Lecture de la matrice finale...")

    df = charger_matrice()

    controles_generaux(df)

    controle_grille_temporelle(df)

    statistiques_globales(df)

    extremes = analyser_extremes(df)

    stats_stations = statistiques_par_station(df)

    stats_annees = statistiques_par_annee(df)

    variations = analyser_variations(df)

    extremes_par_station(df)

    controle_final(df)

    titre("FICHIERS CREES")

    print(
        "Statistiques par station :",
        FICHIER_STATS_STATIONS,
    )

    print(
        "Statistiques par année :",
        FICHIER_STATS_ANNEES,
    )

    print(
        "Températures extrêmes :",
        FICHIER_EXTREMES,
    )

    print(
        "Variations importantes :",
        FICHIER_VARIATIONS,
    )

    titre("VALIDATION TERMINEE")

    print(
        "La matrice originale n'a pas été modifiée."
    )

    print(
        "Aucune température n'a été supprimée "
        "ou corrigée automatiquement."
    )


if __name__ == "__main__":
    main()