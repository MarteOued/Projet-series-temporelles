"""La règle des 14 h : ce qu'on a le droit d'utiliser au moment de la prévision.

À 14 h (heure de Paris) le jour J, on prévoit les 24 heures du jour J+1. La dernière heure
de consommation connue est la tranche 12 h-13 h (config.DERNIERE_HEURE_CONSO_CONNUE = 12) :
la tranche 13 h-14 h se termine à 14 h pile et n'est pas encore publiée.

Tout calcul de variable doit passer par ces fonctions pour ne jamais utiliser une heure
qui n'était pas connue à 14 h (voir docs/protocole.md et notebooks/01_donnees_RTE.ipynb, étape 11).
"""
import pandas as pd

from src import config


def fin_des_donnees_connues(jour_J):
    """Instant (en UTC) où se termine la dernière heure de consommation connue à 14 h le jour J.

    La dernière heure connue est la tranche 12 h-13 h (heure de Paris) : elle se termine à 13 h,
    soit 12 h UTC en hiver et 11 h UTC en été.
    """
    heure_fin = config.DERNIERE_HEURE_CONSO_CONNUE + 1  # 12 + 1 = 13 h
    jour = pd.Timestamp(jour_J).strftime("%Y-%m-%d")
    return pd.Timestamp(f"{jour} {heure_fin:02d}:00", tz=config.FUSEAU).tz_convert("UTC")


def est_connue_a_14h(debut_heure_utc, jour_J):
    """Vrai si l'heure de consommation qui commence à `debut_heure_utc` est connue à 14 h le jour J.

    Une heure est connue seulement si elle est TERMINÉE avant la fin des données connues.
    """
    fin_heure = pd.Timestamp(debut_heure_utc) + pd.Timedelta(hours=1)
    return fin_heure <= fin_des_donnees_connues(jour_J)
