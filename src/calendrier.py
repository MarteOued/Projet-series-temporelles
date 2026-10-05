"""Construction des variables calendaires du projet.

Ce module construit le calendrier utilisé pour prévoir la consommation
électrique du jour J+1.

Les bornes temporelles sont définies dans src/config.py afin de conserver
une configuration unique pour l'ensemble du projet.
"""

import holidays
import pandas as pd

from src.config import DATA_DEBUT, DATA_FIN, DATA_PREPAREES
from src.vacances import construire_indicateurs_vacances

FICHIER_CALENDRIER = DATA_PREPAREES / "calendrier" / "calendrier.csv"


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
        - ferie : 1 pour un jour férié national français, 0 sinon ;
        - veille_ferie, lendemain_ferie, pont_potentiel ;
        - periode_noel : variable CANDIDATE (du 24 décembre au 1er janvier),
          à évaluer sur la validation 2023 avant d'être retenue ;
        - vacances_A, vacances_B, vacances_C, nb_zones_vacances.

    Les variables qui regardent le jour voisin (veille_ferie, lendemain_ferie,
    pont_potentiel) sont calculées sur une période élargie d'un jour de chaque
    côté, puis la table est coupée à [date_debut, date_fin]. Sans cette marge,
    le 31 décembre 2025 ne « verrait » pas que le 1er janvier 2026 est férié.
    """

    # Période demandée, et période élargie d'un jour de chaque côté
    debut_demande = pd.Timestamp(date_debut)
    fin_demandee = pd.Timestamp(date_fin)
    date_debut = (debut_demande - pd.Timedelta(days=1)).date()
    date_fin = (fin_demandee + pd.Timedelta(days=1)).date()

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

    # -------------------------------------------------------------------------
    # 8. Période de Noël (variable candidate)
    # -------------------------------------------------------------------------
    #
    # Du 24 décembre au 1er janvier inclus : les jours les plus atypiques de
    # l'année d'après l'exploration RTE. Variable candidate : son apport sera
    # mesuré sur la validation 2023 avant de la garder dans un modèle.

    jour = calendrier["date"].dt.day
    mois = calendrier["mois"]

    calendrier["periode_noel"] = (
        ((mois == 12) & (jour >= 24))
        | ((mois == 1) & (jour == 1))
    ).astype(int)

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

    # Retour à la période demandée (la marge ne servait qu'aux calculs)
    calendrier = calendrier[
        (calendrier["date"] >= debut_demande)
        & (calendrier["date"] <= fin_demandee)
    ].reset_index(drop=True)

    return calendrier


def main():
    """Télécharge les vacances scolaires si besoin, construit et sauvegarde le calendrier."""

    from src.recuperation_vacances import FICHIER_SORTIE as FICHIER_API
    from src.recuperation_vacances import recuperer_vacances_scolaires
    from src.recuperation_vacances_historiques import construire_calendrier_historique
    from src.vacances import FICHIER_HISTORIQUE

    if not FICHIER_API.exists():
        recuperer_vacances_scolaires()
    if not FICHIER_HISTORIQUE.exists():
        construire_calendrier_historique()

    calendrier = construire_calendrier()

    FICHIER_CALENDRIER.parent.mkdir(parents=True, exist_ok=True)
    calendrier.to_csv(FICHIER_CALENDRIER, index=False)

    print(f"Calendrier : {len(calendrier)} jours, du {calendrier['date'].min():%Y-%m-%d} "
          f"au {calendrier['date'].max():%Y-%m-%d}")
    print("Fichier :", FICHIER_CALENDRIER)


if __name__ == "__main__":
    main()

    