"""Calendriers scolaires historiques manquants dans l'API actuelle.

Ce module complète les années scolaires 2015-2016 et 2016-2017
pour les zones A, B et C.

Les dates proviennent des calendriers officiels du ministère de
l'Éducation nationale.

Sources :
- Bulletin officiel de l'Éducation nationale ;
- calendrier scolaire officiel 2015-2016 ;
- calendrier scolaire officiel 2016-2017.

Ce module ne fusionne pas encore ces données avec celles de l'API.
Il crée uniquement un fichier brut complémentaire qui sera contrôlé
avant toute transformation.
"""

import pandas as pd

from src.config import DATA_RAW


# -----------------------------------------------------------------------------
# Fichier de sortie
# -----------------------------------------------------------------------------

FICHIER_SORTIE = DATA_RAW / "calendrier_scolaire_historique.csv"


# -----------------------------------------------------------------------------
# Périodes officielles
# -----------------------------------------------------------------------------
#
# Convention :
#
# start_date = date officielle de début des vacances
# end_date   = date officielle de reprise des cours
#
# La date de reprise n'est donc pas elle-même un jour de vacances.
#
# Exemple :
#
# start_date = 2016-12-17
# end_date   = 2017-01-03
#
# signifie que la reprise a lieu le 3 janvier 2017.
#
# La transformation en indicatrices quotidiennes sera réalisée plus tard.
# Ici, on conserve simplement les informations officielles.
# -----------------------------------------------------------------------------

PERIODES = [

    # =========================================================================
    # Année scolaire 2015-2016
    # =========================================================================

    # -------------------------------------------------------------------------
    # Vacances de Noël
    # -------------------------------------------------------------------------
    # Mêmes dates pour les zones A, B et C.

    (
        "Vacances de Noël",
        "Zone A",
        "2015-12-19",
        "2016-01-04",
        "2015-2016",
    ),
    (
        "Vacances de Noël",
        "Zone B",
        "2015-12-19",
        "2016-01-04",
        "2015-2016",
    ),
    (
        "Vacances de Noël",
        "Zone C",
        "2015-12-19",
        "2016-01-04",
        "2015-2016",
    ),

    # -------------------------------------------------------------------------
    # Vacances d'Hiver
    # -------------------------------------------------------------------------

    (
        "Vacances d'Hiver",
        "Zone A",
        "2016-02-13",
        "2016-02-29",
        "2015-2016",
    ),
    (
        "Vacances d'Hiver",
        "Zone B",
        "2016-02-06",
        "2016-02-22",
        "2015-2016",
    ),
    (
        "Vacances d'Hiver",
        "Zone C",
        "2016-02-20",
        "2016-03-07",
        "2015-2016",
    ),

    # -------------------------------------------------------------------------
    # Vacances de Printemps
    # -------------------------------------------------------------------------

    (
        "Vacances de Printemps",
        "Zone A",
        "2016-04-09",
        "2016-04-25",
        "2015-2016",
    ),
    (
        "Vacances de Printemps",
        "Zone B",
        "2016-04-02",
        "2016-04-18",
        "2015-2016",
    ),
    (
        "Vacances de Printemps",
        "Zone C",
        "2016-04-16",
        "2016-05-02",
        "2015-2016",
    ),

    # -------------------------------------------------------------------------
    # Vacances d'Été
    # -------------------------------------------------------------------------
    # Début officiel : 5 juillet 2016.
    # Rentrée des élèves : 1er septembre 2016.

    (
        "Vacances d'Été",
        "Zone A",
        "2016-07-05",
        "2016-09-01",
        "2015-2016",
    ),
    (
        "Vacances d'Été",
        "Zone B",
        "2016-07-05",
        "2016-09-01",
        "2015-2016",
    ),
    (
        "Vacances d'Été",
        "Zone C",
        "2016-07-05",
        "2016-09-01",
        "2015-2016",
    ),

    # =========================================================================
    # Année scolaire 2016-2017
    # =========================================================================

    # -------------------------------------------------------------------------
    # Vacances de la Toussaint
    # -------------------------------------------------------------------------
    # Mêmes dates pour les trois zones.

    (
        "Vacances de la Toussaint",
        "Zone A",
        "2016-10-19",
        "2016-11-03",
        "2016-2017",
    ),
    (
        "Vacances de la Toussaint",
        "Zone B",
        "2016-10-19",
        "2016-11-03",
        "2016-2017",
    ),
    (
        "Vacances de la Toussaint",
        "Zone C",
        "2016-10-19",
        "2016-11-03",
        "2016-2017",
    ),

    # -------------------------------------------------------------------------
    # Vacances de Noël
    # -------------------------------------------------------------------------

    (
        "Vacances de Noël",
        "Zone A",
        "2016-12-17",
        "2017-01-03",
        "2016-2017",
    ),
    (
        "Vacances de Noël",
        "Zone B",
        "2016-12-17",
        "2017-01-03",
        "2016-2017",
    ),
    (
        "Vacances de Noël",
        "Zone C",
        "2016-12-17",
        "2017-01-03",
        "2016-2017",
    ),

    # -------------------------------------------------------------------------
    # Vacances d'Hiver
    # -------------------------------------------------------------------------

    (
        "Vacances d'Hiver",
        "Zone A",
        "2017-02-18",
        "2017-03-06",
        "2016-2017",
    ),
    (
        "Vacances d'Hiver",
        "Zone B",
        "2017-02-11",
        "2017-02-27",
        "2016-2017",
    ),
    (
        "Vacances d'Hiver",
        "Zone C",
        "2017-02-04",
        "2017-02-20",
        "2016-2017",
    ),

    # -------------------------------------------------------------------------
    # Vacances de Printemps
    # -------------------------------------------------------------------------

    (
        "Vacances de Printemps",
        "Zone A",
        "2017-04-15",
        "2017-05-02",
        "2016-2017",
    ),
    (
        "Vacances de Printemps",
        "Zone B",
        "2017-04-08",
        "2017-04-24",
        "2016-2017",
    ),
    (
        "Vacances de Printemps",
        "Zone C",
        "2017-04-01",
        "2017-04-18",
        "2016-2017",
    ),

    # -------------------------------------------------------------------------
    # Vacances d'Été
    # -------------------------------------------------------------------------
    # Début officiel : 8 juillet 2017.
    # Rentrée des élèves : 4 septembre 2017.

    (
        "Vacances d'Été",
        "Zone A",
        "2017-07-08",
        "2017-09-04",
        "2016-2017",
    ),
    (
        "Vacances d'Été",
        "Zone B",
        "2017-07-08",
        "2017-09-04",
        "2016-2017",
    ),
    (
        "Vacances d'Été",
        "Zone C",
        "2017-07-08",
        "2017-09-04",
        "2016-2017",
    ),
]


def construire_calendrier_historique():
    """Construit le fichier brut complémentaire 2015-2017.

    Returns
    -------
    pandas.DataFrame
        Une ligne par période de vacances et par zone scolaire.
    """

    # -------------------------------------------------------------------------
    # 1. Construction du DataFrame
    # -------------------------------------------------------------------------

    donnees = pd.DataFrame(
        PERIODES,
        columns=[
            "description",
            "zones",
            "start_date",
            "end_date",
            "annee_scolaire",
        ],
    )

    # -------------------------------------------------------------------------
    # 2. Provenance
    # -------------------------------------------------------------------------
    #
    # On conserve explicitement la provenance afin de distinguer plus tard
    # ces données historiques des données récupérées via l'API.

    donnees["source"] = "bulletin_officiel"

    # -------------------------------------------------------------------------
    # 3. Création du dossier de sortie
    # -------------------------------------------------------------------------

    DATA_RAW.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------------------------------------------------------
    # 4. Sauvegarde
    # -------------------------------------------------------------------------
    #
    # À ce stade aucune transformation métier n'est réalisée.

    donnees.to_csv(
        FICHIER_SORTIE,
        index=False,
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # 5. Contrôle visuel
    # -------------------------------------------------------------------------

    print(donnees.to_string(index=False))

    print()
    print(f"Nombre de lignes : {len(donnees)}")
    print(
        "Valeurs manquantes dans end_date : "
        f"{donnees['end_date'].isna().sum()}"
    )
    print(f"Fichier enregistré : {FICHIER_SORTIE}")

    return donnees


if __name__ == "__main__":
    construire_calendrier_historique()