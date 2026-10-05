"""Tests du module calendrier."""

import pandas as pd

from src.calendrier import construire_calendrier
from src.config import DATA_DEBUT, DATA_FIN



import pytest

from src.vacances import FICHIER_API, FICHIER_HISTORIQUE

# Ces tests lisent les vrais calendriers scolaires : ignorés tant qu'ils ne sont pas
# téléchargés (python -m src.calendrier).
pytestmark = pytest.mark.skipif(
    not (FICHIER_API.exists() and FICHIER_HISTORIQUE.exists()),
    reason="calendriers scolaires absents : lancer python -m src.calendrier",
)

def test_calendrier_bornes():
    """Le calendrier doit commencer et finir aux dates configurées."""

    calendrier = construire_calendrier()

    assert calendrier["date"].iloc[0].date() == DATA_DEBUT
    assert calendrier["date"].iloc[-1].date() == DATA_FIN


def test_calendrier_dates_uniques():
    """Chaque date doit apparaître une seule fois."""

    calendrier = construire_calendrier()

    assert calendrier["date"].is_unique


def test_calendrier_sans_date_manquante():
    """La colonne date ne doit contenir aucune valeur manquante."""

    calendrier = construire_calendrier()

    assert calendrier["date"].notna().all()


def test_calendrier_continu():
    """Deux lignes consécutives doivent toujours être séparées d'un jour."""

    calendrier = construire_calendrier()

    ecarts = calendrier["date"].diff().dropna()

    assert (ecarts == pd.Timedelta(days=1)).all()

def test_jour_semaine():
    """Le numéro du jour doit suivre la convention lundi=0, ..., dimanche=6."""

    calendrier = construire_calendrier()

    # Le 1er décembre 2015 est un mardi.
    ligne = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-01")
    ].iloc[0]

    assert ligne["jour_semaine"] == 1

    # Le 7 décembre 2015 est un lundi.
    ligne = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-07")
    ].iloc[0]

    assert ligne["jour_semaine"] == 0


def test_weekend():
    """Samedi et dimanche doivent être identifiés comme week-end."""

    calendrier = construire_calendrier()

    # Vendredi 4 décembre 2015.
    vendredi = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-04")
    ].iloc[0]

    # Samedi 5 décembre 2015.
    samedi = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-05")
    ].iloc[0]

    # Dimanche 6 décembre 2015.
    dimanche = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-06")
    ].iloc[0]

    assert vendredi["weekend"] == 0
    assert samedi["weekend"] == 1
    assert dimanche["weekend"] == 1


def test_mois():
    """Le mois doit être codé de janvier=1 à décembre=12."""

    calendrier = construire_calendrier()

    decembre = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2015-12-01")
    ].iloc[0]

    janvier = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-01-01")
    ].iloc[0]

    assert decembre["mois"] == 12
    assert janvier["mois"] == 1

def test_jours_feries():
    """Quelques jours fériés nationaux doivent être correctement identifiés."""

    calendrier = construire_calendrier()

    # Lundi de Pâques 2016.
    paques_2016 = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-03-28")
    ].iloc[0]

    # Ascension 2016.
    ascension_2016 = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-05")
    ].iloc[0]

    # Lendemain de l'Ascension : ce jour n'est pas férié.
    lendemain_ascension = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-06")
    ].iloc[0]

    # Lundi de Pâques 2025.
    paques_2025 = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2025-04-21")
    ].iloc[0]

    # Ascension 2025.
    ascension_2025 = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2025-05-29")
    ].iloc[0]

    # Noël 2025.
    noel_2025 = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2025-12-25")
    ].iloc[0]

    assert paques_2016["ferie"] == 1
    assert ascension_2016["ferie"] == 1
    assert lendemain_ascension["ferie"] == 0
    assert paques_2025["ferie"] == 1
    assert ascension_2025["ferie"] == 1
    assert noel_2025["ferie"] == 1

def test_veille_et_lendemain_ferie():
    """La veille et le lendemain d'un jour férié doivent être identifiés."""

    calendrier = construire_calendrier()

    # Mercredi 4 mai 2016 : veille de l'Ascension.
    veille = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-04")
    ].iloc[0]

    # Jeudi 5 mai 2016 : Ascension.
    ascension = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-05")
    ].iloc[0]

    # Vendredi 6 mai 2016 : lendemain de l'Ascension.
    lendemain = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-06")
    ].iloc[0]

    assert veille["ferie"] == 0
    assert veille["veille_ferie"] == 1
    assert veille["lendemain_ferie"] == 0

    assert ascension["ferie"] == 1
    assert ascension["veille_ferie"] == 0
    assert ascension["lendemain_ferie"] == 0

    assert lendemain["ferie"] == 0
    assert lendemain["veille_ferie"] == 0
    assert lendemain["lendemain_ferie"] == 1

def test_pont_potentiel():
    """Les configurations calendaires de pont doivent être identifiées."""

    calendrier = construire_calendrier()

    # Vendredi après l'Ascension 2016 :
    # jeudi 5 mai férié, vendredi 6 mai ouvré, puis week-end.
    vendredi_pont = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-06")
    ].iloc[0]

    # Lundi avant la Toussaint 2016 :
    # week-end, lundi 31 octobre ouvré, mardi 1er novembre férié.
    lundi_pont = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-10-31")
    ].iloc[0]

    # Vendredi ordinaire : ne doit pas être considéré comme un pont.
    vendredi_ordinaire = calendrier.loc[
        calendrier["date"] == pd.Timestamp("2016-05-13")
    ].iloc[0]

    assert vendredi_pont["pont_potentiel"] == 1
    assert lundi_pont["pont_potentiel"] == 1
    assert vendredi_ordinaire["pont_potentiel"] == 0

    # Un pont potentiel doit toujours être un jour ouvré non férié.
    ponts = calendrier.loc[
        calendrier["pont_potentiel"] == 1
    ]

    assert (ponts["weekend"] == 0).all()
    assert (ponts["ferie"] == 0).all()

def test_colonnes_vacances_presentes():
    """Les indicateurs de vacances doivent être présents dans le calendrier."""
    calendrier = construire_calendrier()

    colonnes = {
        "vacances_A",
        "vacances_B",
        "vacances_C",
        "nb_zones_vacances",
    }

    assert colonnes.issubset(calendrier.columns)


def test_vacances_integrees_hiver_2018():
    """Vérifie quelques dates des vacances d'hiver 2018."""
    calendrier = construire_calendrier()

    cas = {
        "2018-02-09": (0, 0, 0, 0),
        "2018-02-10": (1, 0, 0, 1),
        "2018-02-17": (1, 0, 1, 2),
        "2018-02-24": (1, 1, 1, 3),
        "2018-02-26": (0, 1, 1, 2),
        "2018-03-05": (0, 1, 0, 1),
        "2018-03-12": (0, 0, 0, 0),
    }

    for date, attendu in cas.items():
        ligne = calendrier[
            calendrier["date"] == pd.Timestamp(date)
        ]

        assert len(ligne) == 1

        obtenu = tuple(
            ligne.iloc[0][
                [
                    "vacances_A",
                    "vacances_B",
                    "vacances_C",
                    "nb_zones_vacances",
                ]
            ]
        )

        assert obtenu == attendu


def test_nb_zones_vacances_integre():
    """nb_zones_vacances doit être la somme des trois zones."""
    calendrier = construire_calendrier()

    somme = (
        calendrier["vacances_A"]
        + calendrier["vacances_B"]
        + calendrier["vacances_C"]
    )

    assert (
        calendrier["nb_zones_vacances"] == somme
    ).all()

    assert calendrier["nb_zones_vacances"].between(0, 3).all()


def test_indicateurs_vacances_binaires():
    """Les indicateurs A, B et C doivent uniquement valoir 0 ou 1."""
    calendrier = construire_calendrier()

    for colonne in [
        "vacances_A",
        "vacances_B",
        "vacances_C",
    ]:
        assert set(calendrier[colonne].unique()).issubset({0, 1})