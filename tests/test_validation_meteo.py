import numpy as np
import pandas as pd
import pytest

import src.validation_meteo as vm


# =============================================================================
# DONNEES SYNTHETIQUES
# =============================================================================

@pytest.fixture
def matrice_simple():
    """
    Petite matrice météo régulière de fréquence 3 h.
    """
    index = pd.date_range(
        start="2024-01-01 00:00:00",
        periods=5,
        freq="3h",
        tz="UTC",
        name="timestamp",
    )

    return pd.DataFrame(
        {
            "07005": [5.0, 6.0, 7.0, 8.0, 9.0],
            "07481": [10.0, 11.0, 12.0, 13.0, 14.0],
        },
        index=index,
    )


# =============================================================================
# CHARGEMENT
# =============================================================================

def test_charger_matrice(tmp_path, monkeypatch):
    index = pd.date_range(
        "2024-01-01",
        periods=3,
        freq="3h",
        tz="UTC",
    )

    df = pd.DataFrame(
        {
            # volontairement écrit "5" pour vérifier zfill(5)
            "5": [1.0, 2.0, 3.0],
            "7481": [4.0, 5.0, 6.0],
        },
        index=index,
    )

    fichier = tmp_path / "temperatures.csv"
    df.to_csv(fichier)

    monkeypatch.setattr(
        vm,
        "FICHIER_TEMPERATURES",
        fichier,
    )

    resultat = vm.charger_matrice()

    assert resultat.shape == (3, 2)

    assert isinstance(
        resultat.index,
        pd.DatetimeIndex,
    )

    assert str(resultat.index.tz) == "UTC"

    assert resultat.index.name == "timestamp"

    assert list(resultat.columns) == [
        "00005",
        "07481",
    ]

    assert all(
        np.issubdtype(dtype, np.number)
        for dtype in resultat.dtypes
    )


def test_charger_matrice_fichier_absent(tmp_path, monkeypatch):
    fichier = tmp_path / "inexistant.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_TEMPERATURES",
        fichier,
    )

    with pytest.raises(FileNotFoundError):
        vm.charger_matrice()


# =============================================================================
# EXTREMES
# =============================================================================

def test_analyser_extremes(tmp_path, monkeypatch):
    index = pd.date_range(
        "2024-01-01",
        periods=3,
        freq="3h",
        tz="UTC",
        name="timestamp",
    )

    df = pd.DataFrame(
        {
            "07005": [-31.0, 5.0, 46.0],
            "07481": [-30.0, 20.0, 45.0],
        },
        index=index,
    )

    fichier = tmp_path / "extremes.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_EXTREMES",
        fichier,
    )

    extremes = vm.analyser_extremes(df)

    # Les seuils sont stricts :
    # -30 et 45 ne doivent donc pas être signalés.
    assert len(extremes) == 2

    assert set(
        extremes["temperature"].tolist()
    ) == {-31.0, 46.0}

    assert fichier.exists()


def test_analyser_extremes_aucun_extreme(
    matrice_simple,
    tmp_path,
    monkeypatch,
):
    fichier = tmp_path / "extremes.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_EXTREMES",
        fichier,
    )

    extremes = vm.analyser_extremes(
        matrice_simple
    )

    assert extremes.empty
    assert fichier.exists()


# =============================================================================
# STATISTIQUES PAR STATION
# =============================================================================

def test_statistiques_par_station(
    matrice_simple,
    tmp_path,
    monkeypatch,
):
    fichier = tmp_path / "stats_stations.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_STATS_STATIONS",
        fichier,
    )

    stats = vm.statistiques_par_station(
        matrice_simple
    )

    assert stats.shape[0] == 2

    assert list(stats.index) == [
        "07005",
        "07481",
    ]

    colonnes_attendues = {
        "n",
        "moyenne",
        "ecart_type",
        "minimum",
        "q01",
        "q05",
        "mediane",
        "q95",
        "q99",
        "maximum",
    }

    assert set(stats.columns) == colonnes_attendues

    assert stats.loc["07005", "n"] == 5
    assert stats.loc["07005", "moyenne"] == pytest.approx(7.0)
    assert stats.loc["07005", "minimum"] == pytest.approx(5.0)
    assert stats.loc["07005", "maximum"] == pytest.approx(9.0)

    assert stats.loc["07481", "moyenne"] == pytest.approx(12.0)

    assert fichier.exists()


# =============================================================================
# STATISTIQUES PAR ANNEE
# =============================================================================

def test_statistiques_par_annee(
    tmp_path,
    monkeypatch,
):
    index = pd.to_datetime(
        [
            "2023-12-31 21:00:00+00:00",
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 03:00:00+00:00",
        ]
    )

    index.name = "timestamp"

    df = pd.DataFrame(
        {
            "07005": [1.0, 2.0, 3.0],
            "07481": [4.0, 5.0, 6.0],
        },
        index=index,
    )

    fichier = tmp_path / "stats_annees.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_STATS_ANNEES",
        fichier,
    )

    stats = vm.statistiques_par_annee(df)

    assert list(stats.index) == [
        2023,
        2024,
    ]

    # 2023 : deux stations × un timestamp
    assert stats.loc[2023, "n"] == 2

    # 2024 : deux stations × deux timestamps
    assert stats.loc[2024, "n"] == 4

    assert stats.loc[2023, "moyenne"] == pytest.approx(2.5)
    assert stats.loc[2024, "moyenne"] == pytest.approx(4.0)

    assert fichier.exists()


# =============================================================================
# VARIATIONS TEMPORELLES
# =============================================================================

def test_analyser_variations_detecte_variation(
    tmp_path,
    monkeypatch,
):
    index = pd.date_range(
        "2024-01-01",
        periods=4,
        freq="3h",
        tz="UTC",
        name="timestamp",
    )

    df = pd.DataFrame(
        {
            # variation +20 entre les deux premiers points
            "07005": [5.0, 25.0, 26.0, 27.0],

            # aucune variation > 15
            "07481": [10.0, 11.0, 12.0, 13.0],
        },
        index=index,
    )

    fichier = tmp_path / "variations.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_VARIATIONS",
        fichier,
    )

    variations = vm.analyser_variations(df)

    assert len(variations) == 1

    ligne = variations.iloc[0]

    assert ligne["station"] == "07005"
    assert ligne["temperature_precedente"] == pytest.approx(5.0)
    assert ligne["temperature"] == pytest.approx(25.0)
    assert ligne["variation"] == pytest.approx(20.0)
    assert ligne["variation_absolue"] == pytest.approx(20.0)

    assert fichier.exists()


def test_analyser_variations_seuil_strict(
    tmp_path,
    monkeypatch,
):
    """
    Une variation exactement égale à 15 °C
    ne doit pas être signalée puisque le code utilise > 15.
    """
    index = pd.date_range(
        "2024-01-01",
        periods=2,
        freq="3h",
        tz="UTC",
        name="timestamp",
    )

    df = pd.DataFrame(
        {
            "07005": [5.0, 20.0],
        },
        index=index,
    )

    fichier = tmp_path / "variations.csv"

    monkeypatch.setattr(
        vm,
        "FICHIER_VARIATIONS",
        fichier,
    )

    variations = vm.analyser_variations(df)

    assert variations.empty
    assert fichier.exists()


# =============================================================================
# CONTROLE FINAL
# =============================================================================

def test_controle_final_matrice_valide(
    matrice_simple,
    capsys,
):
    vm.controle_final(matrice_simple)

    sortie = capsys.readouterr().out

    assert (
        "Tous les contrôles structurels sont validés."
        in sortie
    )

    assert "Matrice météo finale : OK" in sortie


def test_controle_final_detecte_nan(
    matrice_simple,
    capsys,
):
    df = matrice_simple.copy()
    df.iloc[0, 0] = np.nan

    vm.controle_final(df)

    sortie = capsys.readouterr().out

    assert "contient encore des NaN" in sortie


def test_controle_final_detecte_grille_irreguliere(
    capsys,
):
    index = pd.to_datetime(
        [
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 03:00:00+00:00",
            "2024-01-01 09:00:00+00:00",
        ]
    )

    index.name = "timestamp"

    df = pd.DataFrame(
        {
            "07005": [1.0, 2.0, 3.0],
        },
        index=index,
    )

    vm.controle_final(df)

    sortie = capsys.readouterr().out

    assert (
        "grille temporelle"
        in sortie.lower()
    )


def test_controle_final_detecte_doublon(
    capsys,
):
    index = pd.to_datetime(
        [
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 03:00:00+00:00",
            "2024-01-01 03:00:00+00:00",
        ]
    )

    index.name = "timestamp"

    df = pd.DataFrame(
        {
            "07005": [1.0, 2.0, 3.0],
        },
        index=index,
    )

    vm.controle_final(df)

    sortie = capsys.readouterr().out

    assert "timestamps dupliqués" in sortie


def test_controle_final_detecte_index_non_trie(
    capsys,
):
    index = pd.to_datetime(
        [
            "2024-01-01 03:00:00+00:00",
            "2024-01-01 00:00:00+00:00",
            "2024-01-01 06:00:00+00:00",
        ]
    )

    index.name = "timestamp"

    df = pd.DataFrame(
        {
            "07005": [1.0, 2.0, 3.0],
        },
        index=index,
    )

    vm.controle_final(df)

    sortie = capsys.readouterr().out

    assert "n'est pas trié" in sortie