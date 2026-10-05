"""Tests anti-fuite de la chaîne météo et du calendrier (aucun accès réseau).

Principe commun : on modifie des données « interdites » (le futur, ou les années
2023-2025) et on vérifie que le résultat NE CHANGE PAS. Si une étape utilisait ces
données, le résultat changerait et le test échouerait.
"""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src import (
    benchmark_imputation,
    benchmark_imputation_temporelle,
    calendrier,
    correction_anomalies_meteo,
    imputation_temporelle,
    pipeline_meteo,
    protocole,
    temperature_france,
)


# --- Données synthétiques ---------------------------------------------------------
def matrice_synthetique(debut="2022-10-01", fin="2023-03-31", graine=0):
    """Trois stations corrélées toutes les 3 h, qui traversent la fin de l'apprentissage."""
    index = pd.date_range(debut, fin, freq="3h", tz="UTC")
    rng = np.random.default_rng(graine)
    t = np.arange(len(index))
    commun = 10 + 5 * np.sin(2 * np.pi * t / 8) + np.cumsum(rng.normal(0, 0.3, len(t)))
    return pd.DataFrame({
        "07001": commun + rng.normal(0, 0.5, len(t)),
        "07002": commun + 1 + rng.normal(0, 0.5, len(t)),
        "07003": commun - 1 + rng.normal(0, 0.5, len(t)),
    }, index=index)


def apres_apprentissage(df):
    return df.index >= protocole.fin_apprentissage_utc()


# --- 1. Imputation temporelle : jamais d'observation future -----------------------
@pytest.mark.parametrize("methode", imputation_temporelle.METHODES_CAUSALES)
def test_imputation_temporelle_ne_regarde_pas_le_futur(methode):
    df = matrice_synthetique()[["07001"]]
    df.iloc[400:405, 0] = np.nan                         # trou de 5 points
    resultat, _ = imputation_temporelle.imputer_temporellement(df, {1: methode})

    futur_modifie = df.copy()
    futur_modifie.iloc[405:, 0] += 50.0                  # tout ce qui suit le trou change
    resultat_bis, _ = imputation_temporelle.imputer_temporellement(futur_modifie, {1: methode})

    pd.testing.assert_series_equal(resultat.iloc[400:405, 0], resultat_bis.iloc[400:405, 0])


def test_aucune_methode_non_causale_dans_l_imputation():
    for nom in ["prediction_lineaire", "prediction_journaliere", "prediction_hybride"]:
        assert not hasattr(imputation_temporelle, nom)


# --- 2. Régressions entre stations : apprises sur 2016-2022 seulement --------------
def test_regressions_spatiales_ignorent_2023_2025():
    m = matrice_synthetique()
    voisins = {"07001": ["07002", "07003"], "07002": ["07001", "07003"], "07003": ["07001", "07002"]}
    modeles = benchmark_imputation.ajuster_modeles_adaptatifs(
        protocole.periode_apprentissage(m), voisins)

    m_bis = m.copy()
    m_bis.loc[apres_apprentissage(m_bis)] *= 3          # 2023 complètement différent
    modeles_bis = benchmark_imputation.ajuster_modeles_adaptatifs(
        protocole.periode_apprentissage(m_bis), voisins)

    for station, sous_modeles in modeles.items():
        for cle, modele in sous_modeles.items():
            assert modele["intercept"] == pytest.approx(modeles_bis[station][cle]["intercept"])
            assert np.allclose(modele["coefficients"], modeles_bis[station][cle]["coefficients"])


def test_fin_apprentissage_utc():
    # minuit le 1er janvier 2023 à Paris = 23 h UTC le 31 décembre 2022
    assert protocole.fin_apprentissage_utc() == pd.Timestamp("2022-12-31 23:00", tz="UTC")


# --- 3. Choix de la méthode temporelle : sur l'apprentissage seulement -------------
def test_benchmark_temporel_ne_tire_que_dans_l_apprentissage():
    m = matrice_synthetique()
    fin = protocole.fin_apprentissage_utc()
    for longueur in [1, 8, 16]:
        candidats = benchmark_imputation_temporelle.construire_candidats(m, longueur)
        assert candidats, "aucune séquence candidate"
        for _, debut in candidats:
            # dernière valeur utilisée : le lendemain du dernier point (référence non causale)
            derniere = debut + longueur - 1 + 8
            assert m.index[derniere] < fin


# --- 4. Seuil des anomalies : appris sur l'apprentissage seulement -----------------
def test_seuil_anomalie_ignore_2023_2025():
    m = matrice_synthetique()
    residus = m - m.mean()
    seuil = correction_anomalies_meteo.seuil_spatial_appris(residus, m)

    residus_bis = residus.copy()
    residus_bis.loc[apres_apprentissage(residus_bis)] = 99.0    # énormes écarts après 2022
    assert correction_anomalies_meteo.seuil_spatial_appris(residus_bis, m) == pytest.approx(seuil)


def test_detection_d_anomalie_sur_donnees_synthetiques():
    m = matrice_synthetique()
    observations = m.copy()
    t = m.index[apres_apprentissage(m)][50]
    m.loc[t, "07001"] = -30.0                                    # mesure aberrante
    observations.loc[t, "07001"] = -30.0
    residus = m - m[["07002", "07003"]].mean(axis=1).to_numpy()[:, None]
    seuil = correction_anomalies_meteo.seuil_spatial_appris(residus, observations)
    anomalies = correction_anomalies_meteo.detecter_anomalies(m, observations, residus, seuil)
    assert list(zip(anomalies["timestamp"], anomalies["station"])) == [(t, "07001")]


# --- 5. Température France opérationnelle : jamais d'interpolation vers le futur ---
def test_temperature_horaire_operationnelle_n_utilise_pas_l_observation_suivante():
    index = pd.date_range("2023-01-10", periods=8, freq="3h", tz="UTC")
    obs = pd.DataFrame({"temp_x": np.arange(8, dtype=float)}, index=index)
    horaire = temperature_france.vers_horaire(obs)

    obs_bis = obs.copy()
    obs_bis.iloc[5:] += 100.0                       # observations de 15 h UTC et après modifiées
    horaire_bis = temperature_france.vers_horaire(obs_bis)

    avant_15h = horaire.index < index[5]
    pd.testing.assert_series_equal(horaire.loc[avant_15h, "temp_x"], horaire_bis.loc[avant_15h, "temp_x"])
    # en revanche la version météo parfaite interpole, donc elle change : c'est voulu
    assert not horaire.loc[avant_15h, "temp_x_meteo_parfaite"].equals(
        horaire_bis.loc[avant_15h, "temp_x_meteo_parfaite"])


def test_poids_regionaux_demandes_sur_l_apprentissage(monkeypatch, tmp_path):
    parametres = {}

    class Reponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"code_insee_region": "11", "libelle_region": "IDF",
                                 "consommation_totale": 1.0}]}

    def faux_get(url, params, timeout):
        parametres.update(params)
        return Reponse()

    monkeypatch.setattr(temperature_france, "FICHIER_CONSO_REGIONALE", tmp_path / "conso.csv")
    monkeypatch.setattr(temperature_france.requests, "get", faux_get)
    temperature_france.telecharger_conso_regionale()
    filtre = parametres["where"]
    assert "2016-01-01T00:00:00+01:00" in filtre
    assert "2023-01-01T00:00:00+01:00" in filtre and "<" in filtre   # 2023 exclu
    assert "2024" not in filtre and "2025" not in filtre


def test_poids_regionaux_somment_a_1_et_ponderation():
    conso = pd.DataFrame({"code_insee_region": ["11", "76"], "consommation_totale": [3.0, 1.0]})
    poids = temperature_france.poids_regionaux(conso)
    assert poids.sum() == pytest.approx(1.0)
    temperatures = pd.DataFrame({"A": [10.0], "B": [20.0], "C": [30.0]})
    regions = pd.Series({"A": "11", "B": "76", "C": "76"})
    # IDF = 10 (poids 0,75) ; Occitanie = moyenne(20, 30) = 25 (poids 0,25)
    assert temperature_france.temperature_38_ponderee(temperatures, regions, poids).iloc[0] == \
        pytest.approx(0.75 * 10 + 0.25 * 25)


def test_la_corse_est_exclue_de_la_temperature_france():
    regions = pd.Series({"07149": "11", "07761": "94", "07790": "94"})
    assert temperature_france.stations_continentales(regions) == ["07149"]


# --- 6. Calendrier : bord de la période --------------------------------------------
def test_veille_ferie_le_31_decembre_2025(monkeypatch):
    # Pas besoin des fichiers de vacances pour ce test
    monkeypatch.setattr(calendrier, "construire_indicateurs_vacances",
                        lambda dates: pd.DataFrame({"date": pd.to_datetime(dates)}).assign(
                            vacances_A=0, vacances_B=0, vacances_C=0, nb_zones_vacances=0))
    c = calendrier.construire_calendrier(dt.date(2025, 12, 1), dt.date(2025, 12, 31)).set_index("date")
    assert c.loc["2025-12-31", "veille_ferie"] == 1         # le 1er janvier 2026 est férié
    assert c.index.max() == pd.Timestamp("2025-12-31")      # la marge n'apparaît pas dans la table
    assert c.loc["2025-12-24", "periode_noel"] == 1 and c.loc["2025-12-23", "periode_noel"] == 0


# --- 7. Pipeline : l'ordre des étapes ---------------------------------------------
def test_ordre_du_pipeline_meteo():
    noms = [fonction.__module__ for _, fonction in pipeline_meteo.ETAPES]
    attendu = [
        "src.meteo", "src.imputation_meteo", "src.diagnostic_trous_meteo",
        "src.benchmark_imputation_temporelle", "src.imputation_temporelle",
        "src.correction_anomalies_meteo", "src.diagnostic_anomalies_meteo",
        "src.validation_meteo", "src.temperature_france",
    ]
    assert noms == attendu

def test_benchmark_temporel_exclut_2015():
    """Le benchmark temporel doit utiliser uniquement 2016-2022."""
    import pandas as pd

    from src import protocole
    from src.benchmark_imputation_temporelle import construire_candidats

    # Grille SYNOP 3 h couvrant volontairement 2015 et 2016.
    index = pd.date_range(
        start="2015-12-20 00:00:00",
        end="2016-01-10 00:00:00",
        freq="3h",
        tz="UTC",
    )

    matrice = pd.DataFrame(
        {
            "07149": range(len(index)),
        },
        index=index,
        dtype=float,
    )

    candidats = construire_candidats(
        matrice=matrice,
        longueur=1,
    )

    assert candidats

    timestamps = [
        matrice.index[position]
        for _, position in candidats
    ]

    assert min(timestamps) >= protocole.debut_apprentissage_utc()

    assert all(
        protocole.debut_apprentissage_utc()
        <= timestamp
        < protocole.fin_apprentissage_utc()
        for timestamp in timestamps
    )
