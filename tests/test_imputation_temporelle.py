import numpy as np
import pandas as pd
import pytest

from src.benchmark_imputation_temporelle import (
    calculer_metriques, chevauche,
    prediction_hybride as benchmark_hybride,
    prediction_journaliere as benchmark_journaliere,
    prediction_lineaire as benchmark_lineaire,
    sequence_est_complete,
)
from src.imputation_temporelle import (
    choisir_methode, detecter_sequences_manquantes, imputer_temporellement,
    prediction_hybride, prediction_journaliere, prediction_lineaire,
)

def serie_test(n=30):
    idx = pd.date_range("2025-01-01", periods=n, freq="3h", tz="UTC")
    return pd.Series(np.arange(n, dtype=float), index=idx, name="00001")

def test_detection_sequences():
    s = serie_test(10)
    s.iloc[[1,2,5]] = np.nan
    assert detecter_sequences_manquantes(s) == [
        {"debut_pos":1,"fin_pos":2,"longueur":2},
        {"debut_pos":5,"fin_pos":5,"longueur":1},
    ]

@pytest.mark.parametrize("n,methode", [
    (1,"lineaire"), (2,"hybride"), (3,"hybride"),
    (8,"journaliere"), (4,"non_referencee"),
])
def test_choix_methode(n, methode):
    assert choisir_methode(n) == methode

def test_prediction_lineaire():
    s = serie_test(8)
    s.iloc[2:4] = np.nan
    assert prediction_lineaire(s, 2, 3) == pytest.approx([2.,3.])

def test_prediction_journaliere():
    s = serie_test(25)
    s.iloc[8] = np.nan
    s.iloc[0], s.iloc[16] = 10., 20.
    assert prediction_journaliere(s, 8, 8) == pytest.approx([15.])

def test_prediction_hybride():
    s = serie_test(25)
    s.iloc[8] = np.nan
    s.iloc[7], s.iloc[9] = 12., 18.
    s.iloc[0], s.iloc[16] = 10., 20.
    assert prediction_hybride(s, 8, 8) == pytest.approx([15.])

def test_methodes_benchmark():
    m = serie_test(30).to_frame()
    p1 = benchmark_lineaire(m, "00001", 10, 2)
    p2 = benchmark_journaliere(m, "00001", 10, 2)
    p3 = benchmark_hybride(p1, p2)
    assert p1.shape == p2.shape == p3.shape == (2,)
    assert np.allclose(p3, (p1+p2)/2)

def test_sequence_complete():
    m = serie_test(30).to_frame()
    assert sequence_est_complete(m, "00001", 10, 2)
    m.iloc[9,0] = np.nan
    assert not sequence_est_complete(m, "00001", 10, 2)

def test_chevauche():
    selection = [("00001",10)]
    assert chevauche(("00001",11), selection, 3)
    assert not chevauche(("00001",20), selection, 3)
    assert not chevauche(("00002",11), selection, 3)

def test_metriques():
    s = calculer_metriques([10.,20.], [11.,18.])
    assert s["MAE"] == pytest.approx(1.5)
    assert s["RMSE"] == pytest.approx(np.sqrt(2.5))
    assert s["biais"] == pytest.approx(-0.5)

def test_imputation_finale_un_point():
    idx = pd.date_range("2025-01-01", periods=30, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001":np.arange(30,dtype=float)}, index=idx)
    df.iloc[10,0] = np.nan
    resultat, journal = imputer_temporellement(df)
    assert resultat.iloc[10,0] == pytest.approx(10.)
    assert len(journal) == 1
    assert journal.iloc[0]["methode"] == "lineaire"
