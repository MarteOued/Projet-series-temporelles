"""Construction des variables calendaires du projet.

Ce module construit le calendrier utilisé pour prévoir la consommation
électrique du jour J+1.

Les bornes temporelles sont définies dans src/config.py afin de conserver
une configuration unique pour l'ensemble du projet.
"""

import holidays
import pandas as pd

from src.config import DATA_DEBUT, DATA_FIN
from src.vacances import construire_indicateurs_vacances


def construire_calendrier(
    date_debut=DATA_DEBUT,
    date_fin=DATA_FIN,
):
    """Construit les premières variables calendaires.

    Parameters
    ----------
    date_debut : date
        Première date à inclure.

    date_fin : date
        Dernière date à inclure.

    Returns
    -------
    pandas.DataFrame
        Table contenant une ligne par date avec :
        - date ;
        - jour_semaine : lundi=0, ..., dimanche=6 ;
        - mois : janvier=1, ..., décembre=12 ;
        - weekend : 1 pour samedi/dimanche, 0 sinon ;
        - ferie : 1 pour un jour férié national français, 0 sinon.
    """

    # -------------------------------------------------------------------------
    # 1. Construction de la grille quotidienne
    # -------------------------------------------------------------------------

    dates = pd.date_range(
        start=date_debut,
        end=date_fin,
        freq="D",
    )

    calendrier = pd.DataFrame({
        "date": dates
    })

    # -------------------------------------------------------------------------
    # 2. Jour de la semaine
    # -------------------------------------------------------------------------
    #
    # Convention pandas :
    # lundi=0, mardi=1, mercredi=2, jeudi=3,
    # vendredi=4, samedi=5, dimanche=6.

    calendrier["jour_semaine"] = calendrier["date"].dt.dayofweek

    # -------------------------------------------------------------------------
    # 3. Mois
    # -------------------------------------------------------------------------
    #
    # janvier=1, février=2, ..., décembre=12.

    calendrier["mois"] = calendrier["date"].dt.month

    # -------------------------------------------------------------------------
    # 4. Week-end
    # -------------------------------------------------------------------------
    #
    # samedi  -> jour_semaine = 5
    # dimanche -> jour_semaine = 6
    #
    # La comparaison produit True/False, puis astype(int)
    # transforme True en 1 et False en 0.

    calendrier["weekend"] = (
        calendrier["jour_semaine"] >= 5
    ).astype(int)

    # -------------------------------------------------------------------------
    # 5. Jours fériés nationaux français
    # -------------------------------------------------------------------------
    #
    # Certaines fêtes ont une date fixe (Noël, 14 juillet, etc.)
    # tandis que d'autres changent chaque année
    # (lundi de Pâques, Ascension, lundi de Pentecôte).
    #
    # La bibliothèque holidays permet de construire ces dates
    # automatiquement pour toutes les années de notre période.

    annees = range(
        date_debut.year,
        date_fin.year + 1,
    )

    jours_feries = holidays.France(
        years=annees
    )

    # Conversion de la colonne pandas datetime en objets date
    # pour tester l'appartenance aux jours fériés.
    #
    # True  -> 1
    # False -> 0

    calendrier["ferie"] = (
        calendrier["date"]
        .dt.date
        .isin(jours_feries)
        .astype(int)
    )

        # -------------------------------------------------------------------------
    # 6. Veille et lendemain d'un jour férié
    # -------------------------------------------------------------------------
    #
    # veille_ferie = 1 lorsque le jour suivant est férié.
    #
    # Exemple :
    # mercredi 4 mai 2016 -> jeudi 5 mai férié
    # donc veille_ferie = 1 le mercredi.
    #
    # shift(-1) permet de regarder la valeur du jour suivant.

    calendrier["veille_ferie"] = (
        calendrier["ferie"]
        .shift(-1, fill_value=0)
        .astype(int)
    )

    # lendemain_ferie = 1 lorsque le jour précédent est férié.
    #
    # Exemple :
    # jeudi 5 mai 2016 férié -> vendredi 6 mai
    # donc lendemain_ferie = 1 le vendredi.
    #
    # shift(1) permet de regarder la valeur du jour précédent.

    calendrier["lendemain_ferie"] = (
        calendrier["ferie"]
        .shift(1, fill_value=0)
        .astype(int)
    )

        # -------------------------------------------------------------------------
    # 7. Pont potentiel
    # -------------------------------------------------------------------------
    #
    # On appelle "pont potentiel" un jour ouvré non férié situé entre
    # un jour férié et un week-end.
    #
    # Deux configurations sont retenues :
    #
    # 1. vendredi après un jeudi férié :
    #
    #    jeudi       vendredi       samedi
    #    férié   ->  PONT       ->  week-end
    #
    # 2. lundi avant un mardi férié :
    #
    #    dimanche      lundi         mardi
    #    week-end  ->  PONT      ->  férié
    #
    # La variable décrit donc une possibilité calendaire de faire le pont,
    # et non le comportement réel des personnes.

    vendredi_apres_ferie = (
        (calendrier["jour_semaine"] == 4)
        & (calendrier["lendemain_ferie"] == 1)
    )

    lundi_avant_ferie = (
        (calendrier["jour_semaine"] == 0)
        & (calendrier["veille_ferie"] == 1)
    )

    calendrier["pont_potentiel"] = (
        (
            vendredi_apres_ferie
            | lundi_avant_ferie
        )
        & (calendrier["ferie"] == 0)
        & (calendrier["weekend"] == 0)
    ).astype(int)


        # -------------------------------------------------------------------------
    # Vacances scolaires
    # -------------------------------------------------------------------------

    vacances = construire_indicateurs_vacances(
        calendrier["date"]
    )

    calendrier = calendrier.merge(
        vacances,
        on="date",
        how="left",
        validate="one_to_one",
    )

    colonnes_vacances = [
        "vacances_A",
        "vacances_B",
        "vacances_C",
        "nb_zones_vacances",
    ]

    calendrier[colonnes_vacances] = (
        calendrier[colonnes_vacances]
        .fillna(0)
        .astype(int)
    )

    return calendrier

    