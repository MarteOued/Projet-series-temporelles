"""Tests de la règle des 14 h (src/protocole.py)."""
import pandas as pd

from src.protocole import est_connue_a_14h, fin_des_donnees_connues


def test_fin_des_donnees_connues_en_hiver_et_en_ete():
    # 13 h à Paris = 12 h UTC en hiver, 11 h UTC en été
    assert fin_des_donnees_connues("2023-01-10") == pd.Timestamp("2023-01-10 12:00", tz="UTC")
    assert fin_des_donnees_connues("2023-07-11") == pd.Timestamp("2023-07-11 11:00", tz="UTC")


def test_la_tranche_12h_13h_est_connue_mais_pas_13h_14h():
    jour_J = "2023-01-10"
    tranche_12h = pd.Timestamp("2023-01-10 12:00", tz="Europe/Paris").tz_convert("UTC")
    tranche_13h = pd.Timestamp("2023-01-10 13:00", tz="Europe/Paris").tz_convert("UTC")
    assert est_connue_a_14h(tranche_12h, jour_J)
    assert not est_connue_a_14h(tranche_13h, jour_J)


def test_retards_autorises_pour_chaque_heure_de_J_plus_1():
    """Retard 24 h seulement pour H <= 12 ; retards 48 h et 168 h toujours (docs/protocole.md)."""
    for jour_J in ["2023-01-10", "2023-07-11"]:  # un jour d'hiver et un jour d'été
        lendemain = (pd.Timestamp(jour_J) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for H in range(24):
            cible = pd.Timestamp(f"{lendemain} {H:02d}:00", tz="Europe/Paris")
            retard = {jours: (cible - pd.Timedelta(days=jours)).tz_convert("UTC") for jours in (1, 2, 7)}
            assert est_connue_a_14h(retard[1], jour_J) == (H <= 12)
            assert est_connue_a_14h(retard[2], jour_J)
            assert est_connue_a_14h(retard[7], jour_J)


def test_la_cible_n_est_jamais_connue():
    jour_J = "2023-01-10"
    for H in range(24):
        cible = pd.Timestamp(f"2023-01-11 {H:02d}:00", tz="Europe/Paris").tz_convert("UTC")
        assert not est_connue_a_14h(cible, jour_J)
