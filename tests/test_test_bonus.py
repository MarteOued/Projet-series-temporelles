"""Tests de src/test_bonus.py (fausses données : le vrai test bonus ne se lance qu'une fois)."""
import numpy as np
import pandas as pd

from src import config, features, test_bonus
from src import modeles_lineaires as m1


def test_six_blocs_mensuels_de_2026():
    blocs = test_bonus.blocs_mensuels()
    assert [nom for nom, _, _ in blocs] == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert blocs[0][1] == pd.Timestamp("2026-01-01") and blocs[-1][2] == pd.Timestamp("2026-07-01")


def test_les_jours_de_2026_sont_etiquetes_test_bonus():
    assert features.periode_jour_cible("2025-12-31") == "test"
    assert features.periode_jour_cible("2026-01-01") == "test_bonus"
    assert features.periode_jour_cible("2026-06-30") == "test_bonus"
    assert features.periode_jour_cible("2026-07-01") == "hors_periode"


def faux_dataset():
    jours = pd.date_range("2025-06-01", "2026-06-30", freq="D")
    d = pd.DataFrame({"jour_cible": np.repeat(jours, 24), "heure_cible": np.tile(np.arange(24), len(jours))})
    d["periode"] = [features.periode_jour_cible(j) for j in d["jour_cible"]]
    d["exclu_covid"] = False
    d[m1.COLONNE_CIBLE] = 50_000.0
    d["jour_cible"] = d["jour_cible"].dt.strftime("%Y-%m-%d")
    return d


def test_chaque_mois_n_apprend_que_le_passe():
    donnees = faux_dataset()
    vus = []

    def ajuster(apprentissage):
        vus.append((pd.to_datetime(apprentissage["jour_cible"]).max(),
                    set(apprentissage["periode"])))
        return None

    predictions = test_bonus.predire_par_mois(donnees, ajuster, lambda m, bloc: np.zeros(len(bloc)))
    for (_, debut, _), (dernier, periodes) in zip(test_bonus.blocs_mensuels(), vus):
        assert dernier == debut - pd.Timedelta(days=1)       # tout le passé, rien du mois prévu
    assert "test_bonus" in vus[-1][1]                         # les mois de 2026 déjà passés servent
    assert len(predictions) == 181 * 24
    assert set(predictions["bloc"]) == {nom for nom, _, _ in test_bonus.blocs_mensuels()}


def test_la_liste_des_stations_reste_figee_sur_2015_2025():
    assert config.ANNEES_SELECTION_STATIONS == (2015, 2025)
    assert config.DATA_FIN >= config.TEST_BONUS[1]
