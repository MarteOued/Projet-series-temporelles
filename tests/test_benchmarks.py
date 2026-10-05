"""Tests de src/benchmarks.py sur de fausses données (aucun accès réseau)."""
import numpy as np
import pandas as pd
import pytest

from src import benchmarks

HEURES = list(range(24))


def fausse_conso_horaire(debut, fin):
    """Consommation horaire en UTC dont la valeur dit d'où elle vient : jour x 100 + heure de Paris."""
    index = pd.date_range(
        pd.Timestamp(debut, tz="Europe/Paris"), pd.Timestamp(fin, tz="Europe/Paris"),
        freq="h", inclusive="left",
    ).tz_convert("UTC")
    paris = index.tz_convert("Europe/Paris")
    valeurs = (paris.dayofyear * 100 + paris.hour).astype(float)
    return pd.DataFrame({"consommation_MW": valeurs}, index=index)


def test_tableau_jour_heure_et_changements_d_heure():
    conso_jour = benchmarks.consommation_par_jour(fausse_conso_horaire("2023-03-20", "2023-04-03"))
    assert list(conso_jour.columns) == HEURES
    # 26 mars 2023 : passage à l'heure d'été, l'heure 2 n'existe pas
    assert np.isnan(conso_jour.loc["2023-03-26", 2])
    assert conso_jour.loc["2023-03-27"].notna().all()
    assert conso_jour.loc["2023-03-27", 18] == 86 * 100 + 18


def test_b1_recopie_le_meme_jour_7_jours_avant():
    conso_jour = benchmarks.consommation_par_jour(fausse_conso_horaire("2023-01-01", "2023-02-15"))
    cible = pd.DatetimeIndex(["2023-02-01"])
    b1 = benchmarks.benchmark_b1(conso_jour, cible)
    pd.testing.assert_series_equal(b1.iloc[0], conso_jour.loc["2023-01-25"], check_names=False)


def test_b2_moyenne_des_4_memes_jours():
    conso_jour = benchmarks.consommation_par_jour(fausse_conso_horaire("2023-01-01", "2023-02-15"))
    cible = pd.DatetimeIndex(["2023-02-01"])
    b2 = benchmarks.benchmark_b2(conso_jour, cible)
    attendu = conso_jour.loc[["2023-01-25", "2023-01-18", "2023-01-11", "2023-01-04"]].mean()
    pd.testing.assert_series_equal(b2.iloc[0], attendu, check_names=False)


def test_les_benchmarks_respectent_la_regle_des_14h():
    jours = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    benchmarks.verifier_disponibilite(jours, benchmarks.DECALAGE_B1)   # ne doit pas lever d'erreur
    benchmarks.verifier_disponibilite(jours, benchmarks.DECALAGES_B2)


def test_la_regle_des_14h_detecte_une_triche():
    # Recopier la veille du jour cible (le jour J lui-même) serait une fuite :
    # à 14 h, l'heure 23 h du jour J n'est pas encore connue.
    with pytest.raises(ValueError, match="Fuite"):
        benchmarks.verifier_disponibilite(pd.DatetimeIndex(["2023-01-11"]), [1])


def test_le_test_final_est_protege():
    with pytest.raises(ValueError, match="une fois"):
        benchmarks.evaluer_periode("test")
