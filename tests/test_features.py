"""Test de non-fuite de la table des variables à 14 h (src/features.py).

Principe : à 14 h le jour J, je ne connais que le passé. Si je remplace par
n'importe quoi TOUT ce qui arrive après (consommation après la tranche
12 h-13 h, météo après 13 h), les variables de J+1 ne doivent pas bouger.
Seule la cible (la consommation réelle de J+1) change, puisqu'on la prévoit.

Contrôle inverse : si je change la DERNIÈRE information autorisée, les
variables doivent bouger ; sinon le test ne prouverait rien.
"""
import numpy as np
import pandas as pd
import pytest

from src import config, features, protocole

DEBUT, FIN = "2022-11-01", "2023-08-31"
CIBLE = "consommation_cible_MW"


def fausses_donnees(graine=0):
    rng = np.random.default_rng(graine)
    heures = pd.date_range(f"{DEBUT} 00:00", f"{FIN} 23:00", freq="h", tz="UTC")
    n = len(heures)
    consommation = pd.Series(
        50_000 + 5_000 * np.sin(np.arange(n) * 2 * np.pi / 24) + rng.normal(0, 500, n),
        index=heures, name="consommation_MW",
    )
    base = 10 + 8 * np.sin(np.arange(n) * 2 * np.pi / (24 * 365)) + rng.normal(0, 1, n)
    meteo = pd.DataFrame(
        {nom: base + decalage for nom, decalage in
         zip(features.COLONNES_TEMPERATURE_OPERATIONNELLE, (0.0, 0.3, -0.2))},
        index=heures,
    )
    jours = pd.date_range(DEBUT, FIN, freq="D")
    calendrier = pd.DataFrame(0, index=jours, columns=features.COLONNES_CALENDRIER)
    calendrier["jour_semaine"] = jours.dayofweek
    calendrier["mois"] = jours.month
    calendrier["weekend"] = (jours.dayofweek >= 5).astype(int)
    calendrier.index.name = "date"
    return consommation, meteo, calendrier


def ligne_de_la_cible(consommation, meteo, calendrier, jour_J):
    """Les 24 lignes du jour cible J+1, construites comme dans le vrai pipeline."""
    cible = pd.Timestamp(jour_J) + pd.Timedelta(days=1)
    dataset = features.construire_dataset(consommation, meteo, calendrier, cible, cible)
    assert len(dataset) == 24
    return dataset.set_index("heure_cible")


def brouiller_le_futur(consommation, meteo, jour_J):
    """Remplace tout ce qui n'est pas connu à 14 h le jour J par des valeurs absurdes."""
    consommation, meteo = consommation.copy(), meteo.copy()
    fin_conso = protocole.fin_des_donnees_connues(jour_J)       # fin de la tranche 12 h-13 h
    debut_tranche = consommation.index
    inconnue = debut_tranche + pd.Timedelta(hours=1) > fin_conso
    consommation[inconnue] = 999_999.0
    meteo.loc[meteo.index > protocole.limite_meteo_connue(jour_J)] = 99.0
    return consommation, meteo


JOURS = [
    "2023-01-17",   # hiver : 13 h Paris = 12 h UTC
    "2023-07-12",   # été : 13 h Paris = 11 h UTC
    "2023-03-26",   # jour J de 23 h : l'historique traverse le changement d'heure
]


@pytest.mark.parametrize("jour_J", JOURS)
def test_rien_de_ce_qui_suit_14h_ne_change_les_variables(jour_J):
    consommation, meteo, calendrier = fausses_donnees()
    normal = ligne_de_la_cible(consommation, meteo, calendrier, jour_J)

    conso_brouillee, meteo_brouillee = brouiller_le_futur(consommation, meteo, jour_J)
    brouille = ligne_de_la_cible(conso_brouillee, meteo_brouillee, calendrier, jour_J)

    variables = [c for c in normal.columns if c != CIBLE]
    pd.testing.assert_frame_equal(normal[variables], brouille[variables])
    # la cible, elle, change bien : le brouillage a vraiment eu lieu
    assert (brouille[CIBLE] == 999_999.0).all()


def test_les_jours_de_changement_d_heure_ne_sont_pas_des_cibles():
    consommation, meteo, calendrier = fausses_donnees()
    cible = pd.Timestamp("2023-03-26")
    assert features.construire_dataset(consommation, meteo, calendrier, cible, cible).empty


@pytest.mark.parametrize("jour_J", ["2023-01-17", "2023-07-12"])
def test_la_derniere_consommation_autorisee_compte(jour_J):
    # Contrôle inverse : la tranche 12 h-13 h du jour J est connue à 14 h ;
    # elle doit servir (retard de 24 h) pour prévoir l'heure 12 de J+1.
    consommation, meteo, calendrier = fausses_donnees()
    normal = ligne_de_la_cible(consommation, meteo, calendrier, jour_J)

    tranche_12h = pd.Timestamp(f"{jour_J} 12:00", tz=config.FUSEAU).tz_convert("UTC")
    assert protocole.est_connue_a_14h(tranche_12h, jour_J)
    modifiee = consommation.copy()
    modifiee[tranche_12h] += 10_000
    change = ligne_de_la_cible(modifiee, meteo, calendrier, jour_J)

    assert change.loc[12, "conso_veille_effective_MW"] == normal.loc[12, "conso_veille_effective_MW"] + 10_000
    # l'heure 13 de J+1, elle, ne peut pas utiliser la tranche 13 h-14 h du jour J
    assert change.loc[13, "retard_effectif_h"] == 48


@pytest.mark.parametrize("jour_J", ["2023-01-17", "2023-07-12"])
def test_la_derniere_meteo_autorisee_compte(jour_J):
    consommation, meteo, calendrier = fausses_donnees()
    normal = ligne_de_la_cible(consommation, meteo, calendrier, jour_J)

    limite = protocole.limite_meteo_connue(jour_J)
    modifiee = meteo.copy()
    modifiee.loc[limite] += 5.0
    change = ligne_de_la_cible(consommation, modifiee, calendrier, jour_J)

    for colonne in features.COLONNES_TEMPERATURE_OPERATIONNELLE:
        assert change[f"{colonne}_origine"].iloc[0] == pytest.approx(
            normal[f"{colonne}_origine"].iloc[0] + 5.0
        )


def test_aucune_colonne_meteo_parfaite_dans_le_dataset():
    consommation, meteo, calendrier = fausses_donnees()
    meteo["temp_8_villes_meteo_parfaite"] = 0.0
    dataset = features.construire_dataset(consommation, meteo, calendrier, "2023-01-18", "2023-01-18")
    assert not [c for c in dataset.columns if "meteo_parfaite" in c]
