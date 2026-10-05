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


def test_stations_synop():
    """Vérifie la configuration des stations SYNOP.

    Le choix des stations météo est actuellement ouvert.
    STATIONS_SYNOP peut donc être None.

    Lorsqu'une sélection de stations sera validée, elle devra être
    représentée par un dictionnaire contenant des codes OMM valides
    et uniques.
    """
    stations = config.STATIONS_SYNOP

    # Le choix des stations n'est pas encore arrêté.
    if stations is None:
        return

    assert isinstance(stations, dict)

    codes = list(stations.values())

    assert len(codes) > 0
    assert len(set(codes)) == len(codes)

    assert all(
        isinstance(code, str)
        and len(code) == 5
        and code.startswith("07")
        for code in codes
    )


def test_horizons_des_24_heures_de_j_plus_1():
    assert config.HORIZON_MAX - config.HORIZON_MIN + 1 == 24
    assert config.HORIZON_MIN == 24 - config.HEURE_ORIGINE

def test_test_bonus_2026_apres_le_test_final():
    """Le test bonus 2026 (décision 3) vient strictement après le test 2024-2025."""
    debut_bonus, fin_bonus = config.TEST_BONUS
    assert debut_bonus > config.DECOUPAGE["test"][1]
    assert debut_bonus <= fin_bonus
