"""Règles de disponibilité des données au moment de la prévision.

À 14 h (heure de Paris) le jour J, on prévoit les 24 heures du jour J+1.

Deux types de données observées sont actuellement concernés :

1. Consommation RTE
   La dernière heure de consommation considérée comme connue est la tranche
   12 h-13 h, heure de Paris. La tranche 13 h-14 h se termine à 14 h pile
   et n'est donc pas considérée comme disponible au moment de la prévision.

2. Météo SYNOP
   Les observations SYNOP utilisées dans le projet sont principalement
   disponibles toutes les 3 heures en UTC.

   Pour garantir qu'une observation était effectivement disponible au moment
   de la prévision, on impose une marge opérationnelle d'une heure :
   seules les observations insérées au plus tard à 13 h, heure de Paris,
   peuvent être utilisées pour une prévision lancée à 14 h.

   Cela conduit, sur la grille SYNOP 3 h :
       - en hiver : dernière observation utilisable = 12 h UTC ;
       - en été   : dernière observation utilisable = 09 h UTC.

Cette règle est volontairement prudente. L'audit réalisé sur les 40 stations
métropolitaines stables en 2025 montre que les observations SYNOP sont
généralement insérées quelques minutes après leur heure d'observation.

Toutes les variables construites à partir de données observées doivent
respecter ces fonctions afin d'éviter toute fuite temporelle.
"""

import pandas as pd

from src import config


# ---------------------------------------------------------------------------
# Consommation RTE
# ---------------------------------------------------------------------------

def fin_des_donnees_connues(jour_J):
    """Retourne en UTC la fin de la dernière heure de consommation connue.

    À 14 h heure de Paris le jour J, la dernière tranche considérée comme
    disponible est 12 h-13 h.

    Elle se termine donc à 13 h heure de Paris :
        - 12 h UTC en hiver ;
        - 11 h UTC en été.

    Parameters
    ----------
    jour_J :
        Date du jour où la prévision est réalisée.

    Returns
    -------
    pandas.Timestamp
        Instant correspondant à 13 h heure de Paris, converti en UTC.
    """
    heure_fin = config.DERNIERE_HEURE_CONSO_CONNUE + 1

    jour = pd.Timestamp(jour_J).strftime("%Y-%m-%d")

    return pd.Timestamp(
        f"{jour} {heure_fin:02d}:00",
        tz=config.FUSEAU,
    ).tz_convert("UTC")


def est_connue_a_14h(debut_heure_utc, jour_J):
    """Indique si une heure de consommation est connue à 14 h le jour J.

    Une heure de consommation est considérée comme disponible uniquement
    si elle est entièrement terminée avant la limite définie par
    ``fin_des_donnees_connues``.

    Parameters
    ----------
    debut_heure_utc :
        Début de la tranche horaire de consommation, en UTC.

    jour_J :
        Date du jour où la prévision est réalisée.

    Returns
    -------
    bool
        True si la tranche est disponible, False sinon.
    """
    debut_heure = pd.Timestamp(debut_heure_utc)

    if debut_heure.tzinfo is None:
        debut_heure = debut_heure.tz_localize("UTC")
    else:
        debut_heure = debut_heure.tz_convert("UTC")

    fin_heure = debut_heure + pd.Timedelta(hours=1)

    return fin_heure <= fin_des_donnees_connues(jour_J)


# ---------------------------------------------------------------------------
# Météo SYNOP
# ---------------------------------------------------------------------------

def limite_meteo_connue(jour_J):
    """Retourne l'instant limite d'utilisation des observations météo.

    Pour une prévision effectuée à 14 h heure de Paris, on conserve
    uniquement les observations météo disponibles au plus tard à 13 h
    heure de Paris.

    Cette marge d'une heure évite de supposer qu'une observation réalisée
    juste avant 14 h serait immédiatement disponible.

    Parameters
    ----------
    jour_J :
        Date du jour où la prévision est réalisée.

    Returns
    -------
    pandas.Timestamp
        13 h heure de Paris le jour J, converti en UTC.
    """
    jour = pd.Timestamp(jour_J).strftime("%Y-%m-%d")

    return pd.Timestamp(
        f"{jour} 13:00",
        tz=config.FUSEAU,
    ).tz_convert("UTC")


def derniere_observation_synop_utilisable(jour_J):
    """Retourne la dernière heure SYNOP 3 h utilisable le jour J.

    Les observations SYNOP du projet sont sur une grille principale :
        00, 03, 06, 09, 12, 15, 18 et 21 UTC.

    On cherche la dernière heure de cette grille qui ne dépasse pas
    ``limite_meteo_connue(jour_J)``.

    En pratique :
        - hiver : 13 h Paris = 12 h UTC -> dernière SYNOP = 12 h UTC ;
        - été   : 13 h Paris = 11 h UTC -> dernière SYNOP = 09 h UTC.

    Parameters
    ----------
    jour_J :
        Date du jour où la prévision est réalisée.

    Returns
    -------
    pandas.Timestamp
        Timestamp UTC de la dernière observation SYNOP utilisable.
    """
    limite = limite_meteo_connue(jour_J)

    debut_jour_utc = limite.normalize()

    heures_synop = [
        debut_jour_utc + pd.Timedelta(hours=heure)
        for heure in range(0, 24, 3)
    ]

    heures_utilisables = [
        heure
        for heure in heures_synop
        if heure <= limite
    ]

    return max(heures_utilisables)


def observation_synop_connue_a_14h(validity_time, jour_J):
    """Indique si une observation SYNOP peut être utilisée à 14 h.

    Une observation est utilisable si son ``validity_time`` ne dépasse pas
    la dernière observation SYNOP autorisée par le protocole.

    Cette fonction travaille sur ``validity_time`` car les archives
    historiques 2015-2024 ne fournissent pas systématiquement
    ``insert_time``.

    Parameters
    ----------
    validity_time :
        Heure de validité de l'observation SYNOP.

    jour_J :
        Date du jour où la prévision est réalisée.

    Returns
    -------
    bool
        True si l'observation peut être utilisée, False sinon.
    """
    observation = pd.Timestamp(validity_time)

    if observation.tzinfo is None:
        observation = observation.tz_localize("UTC")
    else:
        observation = observation.tz_convert("UTC")

    return observation <= derniere_observation_synop_utilisable(jour_J)

# ---------------------------------------------------------------------------
# Période d'apprentissage des transformations
# ---------------------------------------------------------------------------

def debut_apprentissage_utc():
    """Premier instant de la période d'apprentissage, en UTC (borne incluse).

    La date de début est définie dans
    ``config.DECOUPAGE["apprentissage"][0]``.

    Elle est interprétée à minuit en heure de Paris puis convertie en UTC,
    afin que toutes les transformations apprises utilisent exactement
    la même période d'apprentissage.
    """
    debut = pd.Timestamp(
        config.DECOUPAGE["apprentissage"][0]
    )

    return debut.tz_localize(config.FUSEAU).tz_convert("UTC")


def fin_apprentissage_utc():
    """Premier instant APRÈS la période d'apprentissage, en UTC (borne exclue).

    Tout paramètre appris sur les données (corrélations, régressions entre
    stations, choix d'une méthode d'imputation, poids régionaux, seuils) doit
    utiliser uniquement les observations comprises dans la période
    d'apprentissage définie dans ``config.DECOUPAGE``.

    La borne retournée correspond à minuit, heure de Paris, le lendemain
    du dernier jour d'apprentissage.
    """
    fin = pd.Timestamp(
        config.DECOUPAGE["apprentissage"][1]
    )

    lendemain = fin + pd.Timedelta(days=1)

    return lendemain.tz_localize(config.FUSEAU).tz_convert("UTC")


def periode_apprentissage(donnees):
    """Extrait exactement la période d'apprentissage.

    Les données doivent être indexées par des timestamps compatibles avec
    les bornes UTC du protocole.

    La sélection appliquée est :

        debut_apprentissage_utc() <= timestamp < fin_apprentissage_utc()

    Ainsi, des observations disponibles avant le début officiel de
    l'apprentissage, notamment celles de 2015, ne peuvent pas participer
    à l'estimation des paramètres du pipeline.
    """
    debut = debut_apprentissage_utc()
    fin = fin_apprentissage_utc()

    return donnees.loc[
        (donnees.index >= debut)
        & (donnees.index < fin)
    ]