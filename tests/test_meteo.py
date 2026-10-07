"""Tests du module src.meteo.

Ces tests vérifient :

1. la lecture correcte des archives SYNOP ;
2. la conservation des codes OMM comme chaînes de caractères ;
3. la conversion correcte des dates et températures ;
4. l'identification des stations stables sur 2015-2025 ;
5. la sélection géographique des stations métropolitaines ;
6. la sélection finale des stations stables métropolitaines.

Les nombres 57, 42 et 40 proviennent de l'audit des données réalisé
avant l'intégration de la sélection dans le module.
"""

import pandas as pd
import pytest

from src.meteo import (
    ANNEE_DEBUT,
    ANNEE_FIN,
    CODES_REGIONS_METROPOLE,
    TOLERANCE_LITTORAL_METRES,
    chemin_archive_synop,
    classer_stations_par_region,
    lire_archive_synop,
    lire_liste_stations_officielles,
    lire_regions_metropolitaines,
    stations_metropolitaines,
    stations_stables,
    stations_stables_metropolitaines,
)



from src import config as _config

# Ces tests lisent les vraies archives SYNOP : ils sont ignorés tant qu'elles ne sont pas
# téléchargées (python -m src.meteo).
pytestmark = pytest.mark.skipif(
    not all((_config.DOSSIER_METEO_BRUT / f"synop_{annee}.csv.gz").exists()
            for annee in range(_config.DATA_DEBUT.year, _config.DATA_FIN.year + 1))
    or not (_config.DOSSIER_METEO_BRUT / "regions_2025.geojson").exists(),
    reason="données SYNOP absentes : lancer python -m src.meteo",
)

# =============================================================================
# LECTURE DES ARCHIVES SYNOP
# =============================================================================

def test_lire_archive_synop_2016():
    """L'archive 2016 doit être lue avec le bon schéma."""

    donnees = lire_archive_synop(2016)

    assert isinstance(donnees, pd.DataFrame)

    assert len(donnees) == 158944

    colonnes_attendues = {
        "geo_id_wmo",
        "name",
        "lat",
        "lon",
        "validity_time",
        "t",
    }

    assert colonnes_attendues.issubset(
        donnees.columns
    )


def test_code_omm_conserve_comme_texte():
    """Les zéros initiaux des codes OMM doivent être conservés."""

    donnees = lire_archive_synop(2016)

    assert isinstance(
        donnees["geo_id_wmo"].dtype,
        pd.StringDtype,
    )

    assert "07005" in set(
        donnees["geo_id_wmo"].dropna()
    )


def test_validity_time_est_en_utc():
    """validity_time doit être interprété comme datetime UTC."""

    donnees = lire_archive_synop(2016)

    assert isinstance(
        donnees["validity_time"].dtype,
        pd.DatetimeTZDtype,
    )

    assert str(
        donnees["validity_time"].dt.tz
    ) == "UTC"


def test_temperature_est_numerique():
    """La température SYNOP doit être numérique."""

    donnees = lire_archive_synop(2016)

    assert pd.api.types.is_numeric_dtype(
        donnees["t"]
    )

    # Première température observée dans l'archive 2016 :
    # Abbeville, 2016-01-01 00:00 UTC.
    assert donnees["t"].notna().any()


def test_annee_hors_periode_refusee():
    """Une année hors de la période du projet doit être refusée."""

    with pytest.raises(ValueError):
        chemin_archive_synop(
            ANNEE_DEBUT - 1
        )

    with pytest.raises(ValueError):
        chemin_archive_synop(
            ANNEE_FIN + 1
        )


# =============================================================================
# STATIONS STABLES
# =============================================================================

def test_nombre_stations_stables():
    """L'audit 2015-2025 doit retrouver 57 stations stables."""

    stations = stations_stables()

    assert len(stations) == 57


def test_stations_stables_presentes_11_ans():
    """Chaque station stable doit être présente pendant les 11 années."""

    stations = stations_stables()

    # Liste figée sur 2015-2025 (décision 7), même si les données vont plus loin
    premiere, derniere = _config.ANNEES_SELECTION_STATIONS

    nombre_annees_attendu = (
        derniere
        - premiere
        + 1
    )

    assert nombre_annees_attendu == 11

    assert (
        stations["nb_annees"]
        == nombre_annees_attendu
    ).all()


def test_codes_stations_stables_uniques():
    """Chaque code OMM doit apparaître une seule fois."""

    stations = stations_stables()

    assert (
        stations["geo_id_wmo"]
        .is_unique
    )


def test_station_lyon_est_stable():
    """Lyon-Saint-Exupéry doit appartenir aux stations stables."""

    stations = stations_stables()

    assert "07481" in set(
        stations["geo_id_wmo"]
    )


def test_belle_ile_n_est_pas_stable():
    """Belle-Île ne doit pas appartenir à l'ensemble stable."""

    stations = stations_stables()

    assert "07207" not in set(
        stations["geo_id_wmo"]
    )


# =============================================================================
# LISTE OFFICIELLE
# =============================================================================

def test_nombre_stations_officielles():
    """La liste officielle utilisée doit contenir 62 stations."""

    stations = (
        lire_liste_stations_officielles()
    )

    assert len(stations) == 62

    assert stations["ID"].is_unique


# =============================================================================
# REGIONS METROPOLITAINES
# =============================================================================

def test_nombre_regions_metropolitaines():
    """Les contours doivent contenir les 13 régions métropolitaines."""

    regions = (
        lire_regions_metropolitaines()
    )

    assert len(regions) == 13

    codes = {
        region["code_region"]
        for region in regions
    }

    assert codes == CODES_REGIONS_METROPOLE


def test_tolerance_littorale_est_100_metres():
    """La tolérance géographique validée doit rester fixée à 100 m."""

    assert TOLERANCE_LITTORAL_METRES == 100


# =============================================================================
# CLASSEMENT GEOGRAPHIQUE
# =============================================================================

def test_classement_conserve_les_62_stations():
    """Le classement doit conserver toutes les stations officielles."""

    classement = (
        classer_stations_par_region()
    )

    assert len(classement) == 62

    assert (
        classement["geo_id_wmo"]
        .is_unique
    )


def test_nombre_stations_metropolitaines():
    """La sélection géographique doit retrouver 42 stations."""

    stations = (
        stations_metropolitaines()
    )

    assert len(stations) == 42


def test_stations_metropolitaines_couvrent_13_regions():
    """Les 42 stations doivent couvrir les 13 régions métropolitaines."""

    stations = (
        stations_metropolitaines()
    )

    assert (
        stations["region"]
        .nunique()
        == 13
    )

    assert stations[
        "code_region"
    ].notna().all()


# =============================================================================
# CAS LITTORAUX
# =============================================================================

@pytest.mark.parametrize(
    "code,region_attendue",
    [
        ("07117", "Bretagne"),
        (
            "07314",
            "Nouvelle-Aquitaine",
        ),
        (
            "07661",
            "Provence-Alpes-Côte d'Azur",
        ),
        (
            "07690",
            "Provence-Alpes-Côte d'Azur",
        ),
    ],
)
def test_stations_littorales_classees(
    code,
    region_attendue,
):
    """Les quatre cas littoraux validés doivent rester métropolitains."""

    stations = (
        stations_metropolitaines()
    )

    station = stations[
        stations["geo_id_wmo"] == code
    ]

    assert len(station) == 1

    assert (
        station.iloc[0]["region"]
        == region_attendue
    )


# =============================================================================
# STATIONS STABLES METROPOLITAINES
# =============================================================================

def test_nombre_stations_stables_metropolitaines():
    """L'intersection 57 stations stables x 42 métropolitaines vaut 40."""

    stations = (
        stations_stables_metropolitaines()
    )

    assert len(stations) == 40


def test_stations_finales_uniques():
    """Les 40 stations finales doivent avoir des codes OMM uniques."""

    stations = (
        stations_stables_metropolitaines()
    )

    assert (
        stations["geo_id_wmo"]
        .is_unique
    )


def test_stations_finales_sont_toutes_stables():
    """Chaque station finale doit appartenir aux 57 stations stables."""

    finales = (
        stations_stables_metropolitaines()
    )

    stables = (
        stations_stables()
    )

    assert set(
        finales["geo_id_wmo"]
    ).issubset(
        set(stables["geo_id_wmo"])
    )


def test_stations_finales_sont_toutes_metropolitaines():
    """Chaque station finale doit appartenir aux 42 métropolitaines."""

    finales = (
        stations_stables_metropolitaines()
    )

    metro = (
        stations_metropolitaines()
    )

    assert set(
        finales["geo_id_wmo"]
    ).issubset(
        set(metro["geo_id_wmo"])
    )


def test_stations_finales_couvrent_13_regions():
    """Les stations finales doivent conserver les 13 régions."""

    stations = (
        stations_stables_metropolitaines()
    )

    assert (
        stations["region"]
        .nunique()
        == 13
    )


def test_belle_ile_exclue_des_stations_finales():
    """Belle-Île est métropolitaine mais non stable."""

    stations = (
        stations_stables_metropolitaines()
    )

    assert "07207" not in set(
        stations["geo_id_wmo"]
    )


def test_cap_cepet_exclue_des_stations_finales():
    """Cap Cepet est métropolitaine mais absente des archives étudiées."""

    stations = (
        stations_stables_metropolitaines()
    )

    assert "07661" not in set(
        stations["geo_id_wmo"]
    )


def test_lyon_presente_dans_stations_finales():
    """Lyon-Saint-Exupéry doit appartenir à l'ensemble final."""

    stations = (
        stations_stables_metropolitaines()
    )

    lyon = stations[
        stations["geo_id_wmo"]
        == "07481"
    ]

    assert len(lyon) == 1

    assert (
        lyon.iloc[0]["region"]
        == "Auvergne-Rhône-Alpes"
    )


def test_repartition_regionale_finale():
    """La répartition régionale doit reproduire l'audit validé."""

    stations = (
        stations_stables_metropolitaines()
    )

    attendu = {
        "Auvergne-Rhône-Alpes": 4,
        "Bourgogne-Franche-Comté": 1,
        "Bretagne": 3,
        "Centre-Val de Loire": 2,
        "Corse": 2,
        "Grand Est": 5,
        "Hauts-de-France": 2,
        "Normandie": 4,
        "Nouvelle-Aquitaine": 5,
        "Occitanie": 7,
        "Pays de la Loire": 1,
        "Provence-Alpes-Côte d'Azur": 3,
        "Île-de-France": 1,
    }

    observe = (
        stations["region"]
        .value_counts()
        .to_dict()
    )

    assert observe == attendu