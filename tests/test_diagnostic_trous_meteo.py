import numpy as np
import pandas as pd

from src.diagnostic_trous_meteo import (
    extraire_valeurs_residuelles, identifier_timestamps_vides,
    construire_sequences, ajouter_contexte_temporel,
)

def matrice_test():
    idx = pd.date_range("2025-01-01", periods=8, freq="3h", tz="UTC")
    return pd.DataFrame({
        "00001":[10.,np.nan,np.nan,13.,14.,np.nan,16.,17.],
        "00002":[20.,21.,22.,23.,np.nan,25.,26.,27.]
    }, index=idx)

def test_extraire_valeurs_residuelles():
    valeurs = extraire_valeurs_residuelles(matrice_test())
    assert len(valeurs) == 4
    assert list(valeurs.columns) == ["timestamp", "station"]

def test_identifier_timestamp_vide():
    m = matrice_test()
    m.iloc[4, :] = np.nan
    assert list(identifier_timestamps_vides(m)) == [m.index[4]]

def test_construire_sequences():
    m = matrice_test()
    seq = construire_sequences(extraire_valeurs_residuelles(m))
    s1 = seq[seq["station"] == "00001"]
    assert sorted(s1["nombre_points"].tolist()) == [1, 2]
    longue = s1[s1["nombre_points"] == 2].iloc[0]
    assert longue["duree_ecoulee_heures"] == 3
    assert longue["duree_grille_heures"] == 6

def test_contexte_temporel():
    m = matrice_test()
    seq = construire_sequences(extraire_valeurs_residuelles(m))
    res = ajouter_contexte_temporel(seq, m)
    ligne = res[(res["station"]=="00001") & (res["nombre_points"]==2)].iloc[0]
    assert bool(ligne["encadree"])
    assert ligne["temperature_avant"] == 10.
    assert ligne["temperature_apres"] == 13.

def test_aucun_trou():
    idx = pd.date_range("2025-01-01", periods=4, freq="3h", tz="UTC")
    m = pd.DataFrame({"00001":[1.,2.,3.,4.]}, index=idx)
    valeurs = extraire_valeurs_residuelles(m)
    assert valeurs.empty
    assert construire_sequences(valeurs).empty
