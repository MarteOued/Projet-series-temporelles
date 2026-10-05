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
    prediction_persistance, prediction_persistance_ajustee, prediction_veille,
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

# --- Méthodes causales (le passé seulement) -------------------------------------

def test_prediction_persistance():
    s = serie_test(12).to_numpy(copy=True)
    s[8:10] = np.nan
    assert prediction_persistance(s, 8, 9) == pytest.approx([7., 7.])

def test_prediction_veille():
    s = serie_test(20).to_numpy(copy=True)
    s[10:12] = np.nan
    # même heure la veille = 8 positions avant (3 h x 8 = 24 h)
    assert prediction_veille(s, 10, 11) == pytest.approx([2., 3.])

def test_prediction_veille_recule_si_la_veille_est_dans_le_trou():
    s = serie_test(30).to_numpy(copy=True)
    s[10:22] = np.nan                        # trou de 12 points (36 h)
    p = prediction_veille(s, 10, 21)
    assert p[0] == pytest.approx(2.)         # position 10 -> 2 (la veille)
    assert p[11] == pytest.approx(5.)        # position 21 -> 13 est dans le trou -> 5 (2 jours avant)

def test_prediction_persistance_ajustee():
    s = np.array([10,11,12,13,14,15,16,17, 20,21,22,23,24,25,26,27, 30,np.nan,np.nan,33], float)
    # dernière obs = 30 (pos 16) ; la veille : pos 8 = 20, puis 21 et 22
    assert prediction_persistance_ajustee(s, 17, 18) == pytest.approx([31., 32.])

@pytest.mark.parametrize("longueur,attendu", [
    (1, "a"), (2, "a"), (3, "b"), (5, "b"), (8, "c"), (40, "c"),
])
def test_choix_methode_pour_toute_longueur(longueur, attendu):
    choix = {1: "a", 3: "b", 8: "c"}
    assert choisir_methode(longueur, choix) == attendu

def test_imputation_finale_un_point():
    idx = pd.date_range("2025-01-01", periods=30, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001":np.arange(30,dtype=float)}, index=idx)
    df.iloc[10,0] = np.nan
    resultat, journal = imputer_temporellement(df, {1: "persistance"})
    assert resultat.iloc[10,0] == pytest.approx(9.)   # dernière valeur connue
    assert len(journal) == 1
    assert journal.iloc[0]["methode"] == "persistance"

def test_imputation_trou_de_longueur_quelconque():
    idx = pd.date_range("2025-01-01", periods=40, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001": np.arange(40, dtype=float)}, index=idx)
    df.iloc[20:25, 0] = np.nan                         # 5 points : longueur non testée
    resultat, journal = imputer_temporellement(df, {1: "veille", 8: "persistance"})
    assert resultat["00001"].notna().all()
    assert set(journal["methode_choisie"]) == {"veille"}   # 5 -> règle de la longueur 1

def test_repli_si_la_methode_choisie_est_impossible():
    idx = pd.date_range("2025-01-01", periods=12, freq="3h", tz="UTC")
    df = pd.DataFrame({"00001": np.arange(12, dtype=float)}, index=idx)
    df.iloc[3, 0] = np.nan                              # pas de veille disponible (début de série)
    resultat, journal = imputer_temporellement(df, {1: "veille"})
    assert resultat.iloc[3, 0] == pytest.approx(2.)     # repli sur la persistance
    assert journal.iloc[0]["methode"] == "persistance"

# --- Benchmark : références non causales et outils (inchangés) ------------------

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

def test_sequence_complete_exige_la_veille_du_point_precedent():
    m = serie_test(30).to_frame()
    m.iloc[1,0] = np.nan          # veille du point qui précède la séquence (9 - 8)
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
