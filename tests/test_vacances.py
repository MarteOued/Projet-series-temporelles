"""Tests du module src.vacances."""

import pandas as pd

from src.vacances import (
    VACANCES_CONSERVEES,
    ZONES,
    charger_vacances_api,
    charger_vacances_historiques,
    construire_periodes_vacances,
)



import pytest

from src.vacances import FICHIER_API, FICHIER_HISTORIQUE

# Ces tests lisent les vrais calendriers scolaires : ignorés tant qu'ils ne sont pas
# téléchargés (python -m src.calendrier).
pytestmark = pytest.mark.skipif(
    not (FICHIER_API.exists() and FICHIER_HISTORIQUE.exists()),
    reason="calendriers scolaires absents : lancer python -m src.calendrier",
)

def test_nombre_periodes_api():
    """L'API doit fournir 9 années x 3 zones x 5 vacances."""
    vacances = charger_vacances_api()

    assert len(vacances) == 135


def test_nombre_periodes_historiques():
    """Le complément historique doit contenir 27 périodes."""
    vacances = charger_vacances_historiques()

    assert len(vacances) == 27


def test_nombre_periodes_total():
    """La fusion doit contenir 162 périodes."""
    vacances = construire_periodes_vacances()

    assert len(vacances) == 162


def test_zones():
    """Seules les zones scolaires A, B et C doivent être présentes."""
    vacances = construire_periodes_vacances()

    assert set(vacances["zones"].unique()) == set(ZONES)


def test_types_vacances():
    """Seules les cinq catégories de vacances retenues sont présentes."""
    vacances = construire_periodes_vacances()

    assert set(vacances["description"].unique()) == VACANCES_CONSERVEES


def test_pas_pont_ascension():
    """Le Pont de l'Ascension ne fait pas partie des vacances scolaires."""
    vacances = construire_periodes_vacances()

    assert "Pont de l'Ascension" not in vacances["description"].values


def test_pas_valeurs_manquantes():
    """Les variables nécessaires ne doivent contenir aucune valeur manquante."""
    vacances = construire_periodes_vacances()

    colonnes = [
        "annee_scolaire",
        "zones",
        "description",
        "debut",
        "fin",
        "source",
    ]

    assert not vacances[colonnes].isna().any().any()


def test_dates_coherentes():
    """Une période ne peut pas finir avant de commencer."""
    vacances = construire_periodes_vacances()

    assert (vacances["fin"] >= vacances["debut"]).all()


def test_pas_doublons():
    """Une même période ne doit pas apparaître plusieurs fois."""
    vacances = construire_periodes_vacances()

    colonnes = [
        "annee_scolaire",
        "zones",
        "description",
        "debut",
        "fin",
    ]

    assert not vacances.duplicated(subset=colonnes).any()


def test_nombre_par_annee():
    """Contrôle du nombre de périodes par année scolaire."""
    vacances = construire_periodes_vacances()

    nombres = vacances.groupby("annee_scolaire").size()

    assert nombres["2015-2016"] == 12

    for annee in [
        "2016-2017",
        "2017-2018",
        "2018-2019",
        "2019-2020",
        "2020-2021",
        "2021-2022",
        "2022-2023",
        "2023-2024",
        "2024-2025",
        "2025-2026",
    ]:
        assert nombres[annee] == 15


def test_conversion_utc_date_locale():
    """Vérifie une date connue après conversion UTC -> Europe/Paris."""
    vacances = charger_vacances_api()

    ligne = vacances[
        (vacances["annee_scolaire"] == "2017-2018")
        & (vacances["zones"] == "Zone A")
        & (vacances["description"] == "Vacances d'Été")
    ]

    assert len(ligne) == 1

    assert ligne.iloc[0]["debut"] == pd.Timestamp("2018-07-07")
    assert ligne.iloc[0]["fin"] == pd.Timestamp("2018-09-03")


def test_historique_noel_2015():
    """Vérifie une période historique connue."""
    vacances = charger_vacances_historiques()

    ligne = vacances[
        (vacances["annee_scolaire"] == "2015-2016")
        & (vacances["zones"] == "Zone A")
        & (vacances["description"] == "Vacances de Noël")
    ]

    assert len(ligne) == 1

    assert ligne.iloc[0]["debut"] == pd.Timestamp("2015-12-19")
    assert ligne.iloc[0]["fin"] == pd.Timestamp("2016-01-04")

def test_indicateurs_vacances_hiver_2018():
    """Vérifie les indicateurs pendant les vacances d'hiver 2018."""
    from src.vacances import construire_indicateurs_vacances

    dates = pd.Series(
        pd.to_datetime(
            [
                "2018-02-09",
                "2018-02-10",
                "2018-02-17",
                "2018-02-24",
                "2018-02-26",
                "2018-03-05",
                "2018-03-12",
            ]
        )
    )

    resultat = construire_indicateurs_vacances(dates)

    attendu = [
        # A, B, C, nombre de zones
        (0, 0, 0, 0),  # 09/02
        (1, 0, 0, 1),  # 10/02 : début zone A
        (1, 0, 1, 2),  # 17/02 : début zone C
        (1, 1, 1, 3),  # 24/02 : les trois zones
        (0, 1, 1, 2),  # 26/02 : reprise zone A
        (0, 1, 0, 1),  # 05/03 : reprise zone C
        (0, 0, 0, 0),  # 12/03 : reprise zone B
    ]

    obtenu = list(
        resultat[
            [
                "vacances_A",
                "vacances_B",
                "vacances_C",
                "nb_zones_vacances",
            ]
        ].itertuples(index=False, name=None)
    )

    assert obtenu == attendu


def test_date_fin_exclue():
    """La date de reprise ne doit pas être marquée comme vacances."""
    from src.vacances import construire_indicateurs_vacances

    dates = pd.Series(
        pd.to_datetime(
            [
                "2018-02-25",
                "2018-02-26",
            ]
        )
    )

    resultat = construire_indicateurs_vacances(dates)

    # Zone A : vacances jusqu'au 25 inclus,
    # reprise le 26 février.
    assert resultat.loc[0, "vacances_A"] == 1
    assert resultat.loc[1, "vacances_A"] == 0


def test_nombre_zones_vacances():
    """Le nombre de zones doit être la somme des trois indicatrices."""
    from src.vacances import construire_indicateurs_vacances

    dates = pd.Series(
        pd.date_range(
            "2015-12-01",
            "2025-12-31",
            freq="D",
        )
    )

    resultat = construire_indicateurs_vacances(dates)

    somme = (
        resultat["vacances_A"]
        + resultat["vacances_B"]
        + resultat["vacances_C"]
    )

    assert (
        resultat["nb_zones_vacances"] == somme
    ).all()

    assert resultat["nb_zones_vacances"].between(0, 3).all()
