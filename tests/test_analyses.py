"""Tests de src/analyses.py (fausses données, aucun fichier réel)."""
import numpy as np
import pandas as pd
import pytest

from src import analyses
from src import modeles_lineaires as m1


def faux_dataset():
    jours = pd.date_range("2021-01-01", "2023-12-31", freq="D")
    n = len(jours) * 24
    rng = np.random.default_rng(0)
    d = pd.DataFrame({
        "jour_cible": np.repeat(jours, 24),
        "heure_cible": np.tile(np.arange(24), len(jours)),
    })
    d["periode"] = np.where(d["jour_cible"].dt.year == 2023, "validation", "apprentissage")
    d["exclu_covid"] = False
    d["jour_semaine"] = d["jour_cible"].dt.dayofweek
    d["mois"] = d["jour_cible"].dt.month
    for colonne in ["conso_veille_effective_MW", "conso_lag48_MW", "conso_lag168_MW"]:
        d[colonne] = 50_000 + rng.normal(0, 1_000, n)
    d["retard_effectif_h"] = np.where(d["heure_cible"] <= 12, 24, 48)
    for colonne in m1.VARIABLES_CALENDRIER_BINAIRES_M1:
        d[colonne] = 0
    d[m1.COLONNE_CIBLE] = 0.5 * d["conso_lag48_MW"] + 25_000 + 100 * d["heure_cible"]
    d["jour_cible"] = d["jour_cible"].dt.strftime("%Y-%m-%d")
    return d


def test_chaque_bloc_n_apprend_que_le_passe():
    donnees = faux_dataset()
    derniers_jours = []

    def ajuster(apprentissage):
        derniers_jours.append(pd.to_datetime(apprentissage["jour_cible"]).max())
        return None

    predictions = analyses.predire_par_blocs(donnees, "validation", ajuster,
                                             lambda modele, bloc: np.zeros(len(bloc)))
    for (_, debut, _), dernier in zip(m1.BLOCS_VALIDATION_2023, derniers_jours):
        assert dernier < debut
    assert len(predictions) == 365 * 24
    assert set(predictions["bloc"]) == {"T1", "T2", "T3", "T4"}


def test_un_seul_modele_retrouve_une_relation_simple():
    predictions = analyses.un_seul_modele_m1(faux_dataset())
    erreur = (predictions["prediction_MW"] - predictions[m1.COLONNE_CIBLE]).abs().max()
    assert erreur < 1e-3          # cible = combinaison linéaire exacte des variables


def test_les_variables_du_plafond_ne_sont_pas_dans_le_modele_deployable():
    # Le plafond utilise la vraie météo du jour cible : jamais dans M2
    for heure in range(24):
        variables = m1.variables_m1(heure)
        assert not set(analyses.VARIABLES_PLAFOND) & set(variables)


def test_saisons():
    assert analyses.SAISONS[1] == "hiver" and analyses.SAISONS[7] == "été"
    assert len(analyses.SAISONS) == 12


def test_significativite_compare_la_reference_a_chaque_methode():
    rng = np.random.default_rng(3)
    jours = pd.date_range("2024-01-01", periods=200, freq="D")
    reel = pd.DataFrame(50_000 + rng.normal(0, 1_000, (200, 24)), index=jours, columns=range(24))
    previsions = {
        "M2 : M1 + température": reel + rng.normal(0, 500, (200, 24)),
        "pareil": reel + rng.normal(0, 500, (200, 24)),
        "moins bon": reel + rng.normal(0, 3_000, (200, 24)),
    }
    t = analyses.significativite(reel, previsions)
    assert set(t["autre_methode"]) == {"pareil", "moins bon"}
    assert set(t["perte"]) == {"MAE", "RMSE"}
    conclusions = t.set_index(["autre_methode", "perte"])["conclusion"]
    assert conclusions[("moins bon", "MAE")] == "référence meilleure"
    assert conclusions[("pareil", "MAE")] == "écart non significatif"
