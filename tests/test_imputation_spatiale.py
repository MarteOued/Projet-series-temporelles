import numpy as np
import pandas as pd
import pytest

from src.benchmark_imputation import creer_benchmark_aleatoire, evaluer_predictions
from src.imputation_meteo import extraire_valeurs_manquantes, imputer_valeurs_manquantes, verifier_imputation

def matrice_test():
    idx = pd.date_range("2025-01-01", periods=8, freq="3h", tz="UTC")
    return pd.DataFrame({
        "00001": np.arange(10., 18.),
        "00002": np.arange(20., 28.),
        "00003": np.arange(30., 38.),
    }, index=idx)

def test_benchmark_masque_sans_modifier_original():
    m = matrice_test()
    original = m.copy(deep=True)
    b, verite = creer_benchmark_aleatoire(m, taux=0.25, graine=42)
    pd.testing.assert_frame_equal(m, original)
    assert len(verite) == int(0.25 * m.notna().sum().sum())
    assert int(b.isna().sum().sum()) == len(verite)
    for x in verite.itertuples(index=False):
        assert pd.isna(b.at[x.timestamp, x.station])
        assert m.at[x.timestamp, x.station] == x.temperature_reelle

def test_benchmark_reproductible():
    m = matrice_test()
    b1, v1 = creer_benchmark_aleatoire(m, taux=0.25, graine=42)
    b2, v2 = creer_benchmark_aleatoire(m, taux=0.25, graine=42)
    pd.testing.assert_frame_equal(b1, b2)
    pd.testing.assert_frame_equal(v1, v2)

def test_metriques_benchmark():
    r = pd.DataFrame({"temperature_reelle":[10.,20.,30.],
                      "temperature_predite":[11.,18.,np.nan]})
    s = evaluer_predictions(r)
    assert s["n_total"] == 3
    assert s["n_predites"] == 2
    assert s["couverture_pct"] == pytest.approx(200/3)
    assert s["mae"] == pytest.approx(1.5)
    assert s["rmse"] == pytest.approx(np.sqrt(2.5))

def test_extraire_et_imputer_valeur_manquante():
    m = matrice_test()
    ts = m.index[2]
    m.at[ts, "00001"] = np.nan
    manquantes = extraire_valeurs_manquantes(m)
    assert len(manquantes) == 1
    modeles = {"00001": {("00002",): {
        "intercept": 1.0, "coefficients": np.array([0.5])
    }}}
    imputee, journal = imputer_valeurs_manquantes(m, manquantes, modeles)
    attendu = 1.0 + 0.5 * m.at[ts, "00002"]
    assert imputee.at[ts, "00001"] == pytest.approx(attendu)
    assert journal.loc[0, "nombre_voisins"] == 1
    controles = verifier_imputation(m, imputee, journal)
    assert controles["nb_imputees"] == 1
    assert controles["nb_restantes"] == 0

def test_sans_voisin_valeur_reste_nan():
    m = matrice_test()
    ts = m.index[3]
    m.at[ts, "00001"] = np.nan
    manquantes = extraire_valeurs_manquantes(m)
    imputee, journal = imputer_valeurs_manquantes(m, manquantes, {})
    assert pd.isna(imputee.at[ts, "00001"])
    assert pd.isna(journal.loc[0, "temperature_imputee"])
    assert journal.loc[0, "nombre_voisins"] == 0
