"""Tests de src/evaluation.py sur de petits exemples calculables à la main."""
import numpy as np
import pandas as pd
import pytest

from src import evaluation

HEURES = list(range(24))


def un_jour(valeurs, date="2023-01-10"):
    return pd.DataFrame([valeurs], index=pd.DatetimeIndex([date]), columns=HEURES, dtype=float)


def test_prevision_parfaite():
    reel = un_jour(np.arange(50_000, 50_024))
    e = evaluation.erreurs_par_jour(reel, reel)
    assert (e[["mae", "rmse", "mape", "biais", "erreur_energie", "erreur_pointe"]] == 0).all(axis=None)
    assert e["ecart_heure_pointe"].iloc[0] == 0


def test_erreur_constante_de_1000_mw():
    reel = un_jour([50_000] * 24)
    prevu = un_jour([51_000] * 24)
    e = evaluation.erreurs_par_jour(reel, prevu).iloc[0]
    assert e["mae"] == 1000 and e["rmse"] == 1000
    assert e["biais"] == 1000                      # on prévoit trop : biais positif
    assert e["mape"] == pytest.approx(2.0)         # 1000 / 50 000 = 2 %
    assert e["erreur_energie"] == 24_000           # 24 heures x 1000 MW = 24 000 MWh


def test_rmse_punit_plus_les_grosses_erreurs():
    reel = un_jour([50_000] * 24)
    prevu = un_jour([50_000] * 23 + [52_400])      # une seule grosse erreur de 2 400 MW
    e = evaluation.erreurs_par_jour(reel, prevu).iloc[0]
    assert e["mae"] == pytest.approx(100)          # 2 400 / 24
    assert e["rmse"] == pytest.approx(np.sqrt(2400 ** 2 / 24))
    assert e["rmse"] > e["mae"]


def test_pointe_et_heure_de_pointe():
    reel = un_jour([50_000] * 24)
    reel[19] = 60_000                              # vraie pointe : 19 h, 60 000 MW
    prevu = un_jour([50_000] * 24)
    prevu[18] = 61_000                             # pointe prévue : 18 h, 61 000 MW
    e = evaluation.erreurs_par_jour(reel, prevu).iloc[0]
    assert e["erreur_pointe"] == 1000
    assert e["ecart_heure_pointe"] == 1


def test_comparaison_sur_les_memes_jours():
    jours = pd.date_range("2023-01-10", periods=3, freq="D")
    reel = pd.DataFrame(50_000.0, index=jours, columns=HEURES)
    complet = reel + 1000
    incomplet = complet.copy()
    incomplet.iloc[1, 5] = np.nan                  # il manque une heure le 2e jour
    scores = evaluation.comparer(reel, {"A": complet, "B": incomplet})
    assert scores.loc["nb_jours"].tolist() == [2, 2]  # le 2e jour est retiré pour TOUTES les méthodes


def test_diebold_mariano_detecte_un_vrai_ecart():
    rng = np.random.default_rng(0)
    a = 1000 + rng.normal(0, 100, 500)
    b = a + 200 + rng.normal(0, 50, 500)          # B se trompe toujours de 200 MW de plus
    resultat = evaluation.diebold_mariano(a, b)
    assert resultat["ecart_moyen"] == pytest.approx(-200, abs=10)
    assert resultat["p_valeur"] < 0.001
    assert resultat["part_jours_A_meilleure"] > 0.99


def test_diebold_mariano_egalite():
    rng = np.random.default_rng(1)
    a = 1000 + rng.normal(0, 100, 500)
    b = 1000 + rng.normal(0, 100, 500)            # deux méthodes équivalentes
    assert evaluation.diebold_mariano(a, b)["p_valeur"] > 0.05


def test_diebold_mariano_symetrique():
    rng = np.random.default_rng(2)
    a, b = rng.normal(0, 1, 100), rng.normal(0.3, 1, 100)
    ab, ba = evaluation.diebold_mariano(a, b), evaluation.diebold_mariano(b, a)
    assert ab["z"] == pytest.approx(-ba["z"]) and ab["p_valeur"] == pytest.approx(ba["p_valeur"])
