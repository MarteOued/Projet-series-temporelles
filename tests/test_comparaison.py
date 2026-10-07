"""Tests de src/comparaison.py (fausses données, aucun fichier réel)."""
import numpy as np
import pandas as pd
import pytest

from src import benchmarks, comparaison


def fausses_predictions(jours, valeur, decalage=0.0):
    return pd.DataFrame({
        "jour_cible": np.repeat(jours.strftime("%Y-%m-%d"), 24),
        "heure_cible": list(range(24)) * len(jours),
        "consommation_cible_MW": valeur,
        "prediction_MW": valeur + decalage,
    })


def test_tableau_jour_heure():
    jours = pd.date_range("2023-01-10", periods=2, freq="D")
    tableau = comparaison.tableau_jour_heure(fausses_predictions(jours, 50_000.0, 100.0))
    assert tableau.shape == (2, 24)
    assert list(tableau.columns) == benchmarks.HEURES
    assert (tableau == 50_100.0).all(axis=None)


def test_le_test_n_est_compare_que_sur_demande():
    with pytest.raises(ValueError, match="une fois"):
        comparaison.comparer_periode("test", test_final=False)


def ecrire_modeles(dossier, jours, cible):
    for code in comparaison.MODELES.values():
        fausses_predictions(jours, cible, 500.0).to_csv(
            dossier / comparaison.FICHIERS_PREDICTIONS["validation"].format(code), index=False
        )


def fausse_conso(valeur):
    index = pd.date_range("2022-11-01", "2024-01-31", freq="h", tz="Europe/Paris").tz_convert("UTC")
    return pd.DataFrame({"consommation_MW": valeur}, index=index)


def test_toutes_les_methodes_sur_les_memes_jours(monkeypatch, tmp_path):
    monkeypatch.setattr(comparaison, "DOSSIER_RESULTATS", tmp_path)
    jours = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    ecrire_modeles(tmp_path, jours[jours != "2023-06-15"], 50_000.0)   # un jour manque aux modèles

    scores, _, _ = comparaison.comparer_periode("validation", conso_h=fausse_conso(50_000.0))

    assert scores.loc["nb_jours"].nunique() == 1                       # mêmes jours pour tous
    for nom in comparaison.MODELES:
        assert scores.loc["MAE (MW)", nom] == pytest.approx(500.0)


def test_cible_differente_de_rte_refusee(monkeypatch, tmp_path):
    monkeypatch.setattr(comparaison, "DOSSIER_RESULTATS", tmp_path)
    ecrire_modeles(tmp_path, pd.date_range("2023-01-01", "2023-12-31", freq="D"), 51_000.0)
    with pytest.raises(ValueError, match="cible"):
        comparaison.comparer_periode("validation", conso_h=fausse_conso(50_000.0))
