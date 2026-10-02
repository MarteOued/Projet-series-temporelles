"""Vérifications rapides de src/config.py (aucun accès réseau)."""
from src import config


def _nb_jours(periode):
    return (periode[1] - periode[0]).days + 1


def test_phases_ordonnees_sans_recouvrement():
    a = config.DECOUPAGE["apprentissage"]
    v = config.DECOUPAGE["validation"]
    t = config.DECOUPAGE["test"]
    assert a[0] <= a[1] < v[0] <= v[1] < t[0] <= t[1]
    assert (v[0] - a[1]).days == 1
    assert (t[0] - v[1]).days == 1


def test_nombre_de_jours_par_phase():
    assert _nb_jours(config.DECOUPAGE["apprentissage"]) == 2557
    assert _nb_jours(config.DECOUPAGE["validation"]) == 365
    assert _nb_jours(config.DECOUPAGE["test"]) == 731
    assert _nb_jours(config.EXCLUSION_COVID) == 62


def test_exclusion_covid_dans_apprentissage_seulement():
    a = config.DECOUPAGE["apprentissage"]
    e = config.EXCLUSION_COVID
    assert a[0] <= e[0] and e[1] <= a[1]


def test_marge_pour_les_retards():
    debut_app = config.DECOUPAGE["apprentissage"][0]
    assert (debut_app - config.DATA_DEBUT).days >= 28
    assert config.DECOUPAGE["test"][1] <= config.DATA_FIN


def test_stations_codes_omm():
    codes = list(config.STATIONS_SYNOP.values())
    assert len(codes) == 8
    assert len(set(codes)) == len(codes)
    assert all(isinstance(c, str) and len(c) == 5 and c.startswith("07") for c in codes)


def test_horizons_des_24_heures_de_j_plus_1():
    assert config.HORIZON_MAX - config.HORIZON_MIN + 1 == 24
    assert config.HORIZON_MIN == 24 - config.HEURE_ORIGINE
