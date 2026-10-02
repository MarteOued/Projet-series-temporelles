"""Données de consommation RTE éCO2mix (responsable : Martino)."""
import pandas as pd


def charger_rte(chemin) -> pd.DataFrame:
    """Charge les données brutes éCO2mix."""
    raise NotImplementedError


def nettoyer_rte(df: pd.DataFrame) -> pd.DataFrame:
    """Doublons, valeurs manquantes/aberrantes, timestamps, changement d'heure."""
    raise NotImplementedError


def vers_horaire(df: pd.DataFrame) -> pd.DataFrame:
    """Passe la consommation au pas horaire (colonne `conso`)."""
    raise NotImplementedError
