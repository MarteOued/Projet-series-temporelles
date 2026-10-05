import numpy as np
import pandas as pd
import pytest

from src.diagnostic_anomalies_meteo import (
    construire_positions_corrigees, detecter_variations, origine_valeur,
)
from src.correction_anomalies_meteo import (
    ajuster_modele, calculer_correlations, meilleurs_voisins, predire_adaptatif,
)

def test_detecter_variation_superieure_15():
    idx = pd.date_range("2025-01-01", periods=4, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001":[10.,12.,30.,31.]}, index=idx)
    a = detecter_variations(df)
    assert len(a) == 1
    assert a.iloc[0]["variation"] == pytest.approx(18.)

def test_seuil_15_est_strict():
    idx = pd.date_range("2025-01-01", periods=2, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001":[10.,25.]}, index=idx)
    assert detecter_variations(df).empty

def test_positions_corrigees():
    j = pd.DataFrame({
        "timestamp":[pd.Timestamp("2025-01-01", tz="UTC")],
        "station":["7650"],
    })
    p = construire_positions_corrigees(j)
    assert (pd.Timestamp("2025-01-01", tz="UTC"), "07650") in p

def test_origine_valeur():
    idx = pd.date_range("2025-01-01", periods=4, freq="3h", tz="UTC")
    cols = ["00001"]
    original = pd.DataFrame([1.,np.nan,np.nan,np.nan], index=idx, columns=cols)
    spatial = pd.DataFrame([1.,2.,np.nan,np.nan], index=idx, columns=cols)
    complet = pd.DataFrame([1.,2.,3.,np.nan], index=idx, columns=cols)
    final = pd.DataFrame([1.,2.,3.,4.], index=idx, columns=cols)
    assert origine_valeur(idx[0],"00001",original,spatial,complet,final,set())=="observee"
    assert origine_valeur(idx[1],"00001",original,spatial,complet,final,set())=="imputation_spatiale"
    assert origine_valeur(idx[2],"00001",original,spatial,complet,final,set())=="imputation_temporelle"
    assert origine_valeur(idx[3],"00001",original,spatial,complet,final,{(idx[3],"00001")})=="correction_anomalie"

def donnees_regression(n=150):
    idx = pd.date_range("2025-01-01", periods=n, freq="3h", tz="UTC")
    x1 = np.linspace(0,20,n)
    x2 = np.linspace(5,25,n)**1.01
    y = 2 + .7*x1 + .2*x2
    return pd.DataFrame({"CIBLE":y,"V1":x1,"V2":x2}, index=idx)

def test_regression_adaptative():
    df = donnees_regression()
    modele = ajuster_modele(df, "CIBLE", ["V1","V2"])
    assert modele is not None
    res = predire_adaptatif(
        df, df.index[20], "CIBLE", ["V1","V2"],
        {("V1","V2"):modele}
    )
    assert res["nombre_voisins"] == 2
    assert res["prediction"] == pytest.approx(df.iloc[20]["CIBLE"], abs=1e-8)

def test_meilleurs_voisins():
    df = donnees_regression()
    corr = calculer_correlations(df)
    voisins = meilleurs_voisins(corr, "CIBLE", n=2)
    assert "CIBLE" not in voisins
    assert len(voisins) == 2
