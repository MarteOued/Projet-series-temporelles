from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# =============================================================================
# CHEMINS
# =============================================================================

RACINE = Path(__file__).resolve().parents[1]

D = RACINE / "data" / "donnees-traitees" / "meteo"

ORIGINAL = D / "temperatures_synop_originales.csv"
SPATIAL = D / "temperatures_synop_imputees.csv"
COMPLET = D / "temperatures_synop_completes.csv"
FINAL = D / "temperatures_synop_finales.csv"

JOURNAL_CORRECTIONS = D / "journal_correction_anomalies.csv"


# =============================================================================
# FONCTION UTILITAIRE
# =============================================================================

def lire(path):
    """
    Lit une matrice de températures SYNOP.

    Le test est ignoré si le fichier réel n'existe pas sur la machine.
    """

    if not path.exists():
        pytest.skip(f"Fichier réel absent : {path}")

    df = pd.read_csv(
        path,
        index_col=0,
        parse_dates=True,
    )

    # Uniformisation de l'index temporel
    df.index = pd.to_datetime(
        df.index,
        utc=True,
    )

    # Uniformisation des identifiants de stations
    df.columns = [
        str(c).zfill(5)
        for c in df.columns
    ]

    return df.sort_index()


# =============================================================================
# TEST 1
# STRUCTURE DE LA MATRICE FINALE
# =============================================================================

def test_structure_finale():
    """
    Vérifie que la matrice finale conserve exactement la structure
    temporelle et spatiale de la matrice originale.
    """

    original = lire(ORIGINAL)
    final = lire(FINAL)

    # Même dimension
    assert original.shape == final.shape

    # Même grille temporelle
    assert original.index.equals(final.index)

    # Mêmes stations
    assert original.columns.equals(final.columns)

    # Aucun timestamp dupliqué
    assert final.index.is_unique

    # Grille temporelle régulière de 3 heures
    ecarts = (
        final.index
        .to_series()
        .diff()
        .dropna()
    )

    assert (
        ecarts == pd.Timedelta(hours=3)
    ).all()


# =============================================================================
# TEST 2
# EVOLUTION DU NOMBRE DE VALEURS MANQUANTES
# =============================================================================

def test_reduction_nan():
    """
    Vérifie que les différentes étapes du pipeline réduisent
    progressivement le nombre de valeurs manquantes.

    Original
        ↓
    Imputation spatiale
        ↓
    Imputation temporelle
        ↓
    Matrice finale
    """

    original = lire(ORIGINAL)
    spatial = lire(SPATIAL)
    complet = lire(COMPLET)
    final = lire(FINAL)

    nombres_nan = [
        int(original.isna().sum().sum()),
        int(spatial.isna().sum().sum()),
        int(complet.isna().sum().sum()),
        int(final.isna().sum().sum()),
    ]

    # Le nombre de NaN ne doit jamais augmenter
    assert (
        nombres_nan[0]
        >= nombres_nan[1]
        >= nombres_nan[2]
        >= nombres_nan[3]
    )

    # La matrice finale doit être complète
    assert nombres_nan[3] == 0


# =============================================================================
# TEST 3
# CONSERVATION DES OBSERVATIONS REELLES
# =============================================================================

def test_observations_originales_conservees_hors_deux_corrections():
    """
    Vérifie que toutes les températures réellement observées
    dans les données originales sont conservées dans la matrice finale,
    à l'exception des deux anomalies explicitement corrigées.

    Les deux observations corrigées sont :

    - MARIGNANE (07650)
      2023-08-09 09:00 UTC

    - ST GIRONS (07627)
      2025-09-23 15:00 UTC
    """

    original = lire(ORIGINAL)
    final = lire(FINAL)

    # Positions réellement observées dans les données originales
    masque = original.notna().copy()

    # Deux anomalies explicitement validées et corrigées
    corrections = [
        (
            pd.Timestamp(
                "2023-08-09 09:00:00+00:00"
            ),
            "07650",
        ),
        (
            pd.Timestamp(
                "2025-09-23 15:00:00+00:00"
            ),
            "07627",
        ),
    ]

    # On retire les deux corrections de la comparaison
    for timestamp, station in corrections:

        if (
            timestamp in masque.index
            and station in masque.columns
        ):
            masque.at[
                timestamp,
                station,
            ] = False

    # Valeurs originales observées
    valeurs_originales = (
        original
        .where(masque)
        .stack()
        .sort_index()
    )

    # Valeurs correspondantes dans la matrice finale
    valeurs_finales = (
        final
        .where(masque)
        .stack()
        .sort_index()
    )

    # Les températures doivent être strictement conservées.
    #
    # check_names=False :
    # le fichier original utilise "validity_time"
    # alors que le fichier final utilise "timestamp".
    # Cette différence de nom d'index n'affecte pas les données.
    pd.testing.assert_series_equal(
        valeurs_originales,
        valeurs_finales,
        check_names=False,
    )


# =============================================================================
# TEST 4
# CONTROLE DES DEUX CORRECTIONS D'ANOMALIES
# =============================================================================

def test_deux_corrections():
    """
    Vérifie que le journal de correction contient exactement
    les deux anomalies validées.
    """

    if not JOURNAL_CORRECTIONS.exists():
        pytest.skip(
            f"Journal absent : {JOURNAL_CORRECTIONS}"
        )

    journal = pd.read_csv(
        JOURNAL_CORRECTIONS
    )

    # Exactement deux corrections
    assert len(journal) == 2

    stations = set(
        journal["station"]
        .astype(str)
        .str.zfill(5)
    )

    # Les deux stations attendues
    assert stations == {
        "07650",
        "07627",
    }


# =============================================================================
# TEST 5
# ABSENCE DE NAN ET DE VALEURS INFINIES
# =============================================================================

def test_final_sans_nan_ni_infini():
    """
    Vérifie que la matrice finale ne contient
    ni NaN ni valeur infinie.
    """

    final = lire(FINAL)

    valeurs = final.to_numpy(
        dtype=float
    )

    assert np.isfinite(
        valeurs
    ).all()