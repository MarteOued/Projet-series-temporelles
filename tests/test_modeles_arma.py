"""Tests de M4 (src/modeles_arma.py) : surtout la règle des 14 h sur les résidus."""
import numpy as np
import pandas as pd
import pytest

from src import config, protocole
from src import modeles_arma as m4

JOUR = pd.Timestamp("2023-03-15")


@pytest.mark.parametrize("heure,jours_avant", [(0, 1), (12, 1), (13, 2), (14, 2), (23, 2)])
def test_dernier_jour_disponible(heure, jours_avant):
    # Prévision de D faite à 14 h le jour D-1 : le résidu de D-1 n'est connu
    # que pour les heures dont la consommation est publiée (jusqu'à 12 h-13 h).
    attendu = JOUR - pd.Timedelta(days=jours_avant)
    assert m4.dernier_jour_disponible(JOUR, heure) == attendu


def test_l_heure_13_n_utilise_pas_la_veille():
    assert config.DERNIERE_HEURE_CONSO_CONNUE == 12
    assert m4.horizon_arma(12) == 1
    assert m4.horizon_arma(13) == 2


def residus_synthetiques(heure, debut, nb_jours, graine=0):
    rng = np.random.default_rng(graine)
    jours = pd.date_range(debut, periods=nb_jours, freq="D")
    residus = np.zeros(nb_jours)
    for i in range(1, nb_jours):                      # erreurs qui se suivent (AR(1))
        residus[i] = 0.7 * residus[i - 1] + rng.normal(0, 100)
    return pd.DataFrame({
        m4.COLONNE_JOUR: jours,
        m4.COLONNE_HEURE: heure,
        m4.COLONNE_CIBLE: 50_000.0 + residus,
        m4.COLONNE_PREDICTION_M1: 50_000.0,
        m4.COLONNE_RESIDU_M1: residus,
    })


@pytest.mark.parametrize("heure", [12, 13, 20])
def test_la_correction_n_utilise_pas_un_residu_inconnu_a_14h(heure):
    historique = residus_synthetiques(heure, "2023-01-01", 60)
    bloc = residus_synthetiques(heure, "2023-03-02", 10, graine=1)

    avant = m4.predire_heure_m4(historique, bloc, heure, p=1, q=0)

    # On change TOUT ce qui n'est pas connu à 14 h la veille de chaque jour
    # cible : si la correction change, M4 regardait le futur.
    for i in range(len(bloc)):
        jour_J = bloc[m4.COLONNE_JOUR].iloc[i] - pd.Timedelta(days=1)
        modifie = bloc.copy()
        # Règle indépendante de M4 : le résidu d'un jour à l'heure H est connu
        # seulement si la consommation de cette heure est publiée à 14 h le jour J.
        inconnus = [
            not protocole.est_connue_a_14h(
                pd.Timestamp(f"{jour.date()} {heure:02d}:00", tz=config.FUSEAU).tz_convert("UTC"),
                jour_J,
            )
            for jour in modifie[m4.COLONNE_JOUR]
        ]
        modifie.loc[inconnus, m4.COLONNE_RESIDU_M1] += 50_000.0

        apres = m4.predire_heure_m4(historique, modifie, heure, p=1, q=0)
        assert apres[m4.COLONNE_CORRECTION_ARMA].iloc[i] == pytest.approx(
            avant[m4.COLONNE_CORRECTION_ARMA].iloc[i]
        )


def test_le_residu_de_la_veille_sert_bien_pour_h_12():
    # Contrôle inverse : pour H = 12, le résidu de la veille est connu et doit compter.
    heure = 12
    historique = residus_synthetiques(heure, "2023-01-01", 60)
    bloc = residus_synthetiques(heure, "2023-03-02", 10, graine=1)
    avant = m4.predire_heure_m4(historique, bloc, heure, p=1, q=0)

    modifie = bloc.copy()
    modifie.loc[0, m4.COLONNE_RESIDU_M1] += 50_000.0          # résidu du 2 mars
    apres = m4.predire_heure_m4(historique, modifie, heure, p=1, q=0)

    assert apres[m4.COLONNE_CORRECTION_ARMA].iloc[1] != pytest.approx(
        avant[m4.COLONNE_CORRECTION_ARMA].iloc[1]
    )
