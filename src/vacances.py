"""Préparation des vacances scolaires métropolitaines.

Ce module construit des périodes de vacances scolaires propres pour les
zones A, B et C à partir de deux sources :

- data/donnees-brutes/calendrier_scolaire.csv :
- data/donnees-brutes/calendrier_scolaire_historique.csv :

Les dates provenant de l'API sont converties de UTC vers Europe/Paris avant
d'extraire la date locale.

Le Pont de l'Ascension n'est pas considéré ici comme une période de vacances
scolaires. Il est traité séparément dans le calendrier.
"""

from pathlib import Path

import pandas as pd

from src.config import DATA_BRUTES, FUSEAU


FICHIER_API = DATA_BRUTES / "calendrier_scolaire.csv"
FICHIER_HISTORIQUE = DATA_BRUTES / "calendrier_scolaire_historique.csv"

ZONES = ("Zone A", "Zone B", "Zone C")

ANNEES_API = (
    "2017-2018",
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023",
    "2023-2024",
    "2024-2025",
    "2025-2026",
)

VACANCES_CONSERVEES = {
    "Vacances de la Toussaint",
    "Vacances de Noël",
    "Vacances d'Hiver",
    "Vacances de Printemps",
    "Vacances d'Été",
}

POPULATION_ELEVES = "Élèves"


def _verifier_fichier(chemin: Path) -> None:
    """Vérifie qu'un fichier source existe."""
    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {chemin}"
        )


def _date_locale_depuis_utc(serie: pd.Series) -> pd.Series:
    """Convertit des horodatages UTC en dates locales Europe/Paris."""
    return (
        pd.to_datetime(serie, utc=True)
        .dt.tz_convert(FUSEAU)
        .dt.normalize()
        .dt.tz_localize(None)
    )


def charger_vacances_api(
    chemin: Path = FICHIER_API,
) -> pd.DataFrame:
    """Prépare les vacances provenant de l'API officielle.

    Pour Toussaint, Noël, Hiver et Printemps, la population vaut "-".
    Pour les vacances d'été, l'API distingue notamment les élèves et les
    enseignants : seules les périodes concernant les élèves sont retenues.

    Returns
    -------
    pandas.DataFrame
        Colonnes :
        annee_scolaire, zones, description, debut, fin, source.
    """
    _verifier_fichier(chemin)

    donnees = pd.read_csv(chemin)

    colonnes_requises = {
        "description",
        "population",
        "start_date",
        "end_date",
        "zones",
        "annee_scolaire",
    }

    manquantes = colonnes_requises - set(donnees.columns)

    if manquantes:
        raise ValueError(
            "Colonnes manquantes dans le fichier API : "
            + ", ".join(sorted(manquantes))
        )

    donnees = donnees[
        donnees["zones"].isin(ZONES)
        & donnees["annee_scolaire"].isin(ANNEES_API)
        & donnees["description"].isin(VACANCES_CONSERVEES)
    ].copy()

    # L'API utilise "-" pour les vacances communes à tous.
    # Pour l'été, elle distingue élèves et enseignants.
    est_ete = donnees["description"] == "Vacances d'Été"

    masque_population = (
        (~est_ete & (donnees["population"] == "-"))
        | (est_ete & (donnees["population"] == POPULATION_ELEVES))
    )

    donnees = donnees[masque_population].copy()

    donnees["debut"] = _date_locale_depuis_utc(
        donnees["start_date"]
    )
    donnees["fin"] = _date_locale_depuis_utc(
        donnees["end_date"]
    )

    vacances = (
        donnees[
            [
                "annee_scolaire",
                "zones",
                "description",
                "debut",
                "fin",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            ["annee_scolaire", "zones", "debut"]
        )
        .reset_index(drop=True)
    )

    vacances["source"] = "api_education"

    return vacances


def charger_vacances_historiques(
    chemin: Path = FICHIER_HISTORIQUE,
) -> pd.DataFrame:
    """Charge et prépare les vacances scolaires historiques."""
    _verifier_fichier(chemin)

    donnees = pd.read_csv(chemin)

    colonnes_requises = {
        "description",
        "zones",
        "start_date",
        "end_date",
        "annee_scolaire",
        "source",
    }

    manquantes = colonnes_requises - set(donnees.columns)

    if manquantes:
        raise ValueError(
            "Colonnes manquantes dans le fichier historique : "
            + ", ".join(sorted(manquantes))
        )

    donnees = donnees[
        donnees["zones"].isin(ZONES)
        & donnees["description"].isin(VACANCES_CONSERVEES)
    ].copy()

    donnees["debut"] = pd.to_datetime(
        donnees["start_date"]
    ).dt.normalize()

    donnees["fin"] = pd.to_datetime(
        donnees["end_date"]
    ).dt.normalize()

    vacances = (
        donnees[
            [
                "annee_scolaire",
                "zones",
                "description",
                "debut",
                "fin",
                "source",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            ["annee_scolaire", "zones", "debut"]
        )
        .reset_index(drop=True)
    )

    return vacances


def construire_periodes_vacances() -> pd.DataFrame:
    """Fusionne les vacances historiques et celles de l'API."""
    historique = charger_vacances_historiques()
    api = charger_vacances_api()

    vacances = pd.concat(
        [historique, api],
        ignore_index=True,
    )

    vacances = (
        vacances
        .drop_duplicates(
            subset=[
                "annee_scolaire",
                "zones",
                "description",
                "debut",
                "fin",
            ]
        )
        .sort_values(
            ["debut", "zones", "description"]
        )
        .reset_index(drop=True)
    )

    if (vacances["fin"] < vacances["debut"]).any():
        raise ValueError(
            "Au moins une période de vacances se termine "
            "avant sa date de début."
        )

    return vacances

def construire_indicateurs_vacances(
    dates: pd.Series,
) -> pd.DataFrame:
    """Construit les indicateurs quotidiens de vacances scolaires.

    Pour chaque date, quatre variables sont créées :

    - vacances_A : 1 si la zone A est en vacances, 0 sinon ;
    - vacances_B : 1 si la zone B est en vacances, 0 sinon ;
    - vacances_C : 1 si la zone C est en vacances, 0 sinon ;
    - nb_zones_vacances : nombre de zones en vacances.

    La date de début est incluse dans les vacances.
    La date de fin correspond à la reprise des cours et est donc exclue.

    Parameters
    ----------
    dates : pandas.Series
        Dates pour lesquelles construire les indicateurs.

    Returns
    -------
    pandas.DataFrame
        DataFrame contenant date et les quatre indicateurs.
    """
    calendrier = pd.DataFrame(
        {
            "date": pd.to_datetime(dates).dt.normalize()
        }
    )

    calendrier["vacances_A"] = 0
    calendrier["vacances_B"] = 0
    calendrier["vacances_C"] = 0

    periodes = construire_periodes_vacances()

    correspondance = {
        "Zone A": "vacances_A",
        "Zone B": "vacances_B",
        "Zone C": "vacances_C",
    }

    for zone, colonne in correspondance.items():
        periodes_zone = periodes[
            periodes["zones"] == zone
        ]

        for periode in periodes_zone.itertuples():
            masque = (
                (calendrier["date"] >= periode.debut)
                & (calendrier["date"] < periode.fin)
            )

            calendrier.loc[masque, colonne] = 1

    calendrier["nb_zones_vacances"] = (
        calendrier[
            [
                "vacances_A",
                "vacances_B",
                "vacances_C",
            ]
        ]
        .sum(axis=1)
        .astype(int)
    )

    return calendrier