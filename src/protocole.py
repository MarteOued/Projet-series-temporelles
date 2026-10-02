"""Protocole commun : fusion et simulation à 14h (Martino + binôme)."""
import pandas as pd


def fusionner(rte: pd.DataFrame, meteo: pd.DataFrame, calendrier: pd.DataFrame) -> pd.DataFrame:
    """Dataset historique : une ligne = une heure."""
    raise NotImplementedError


def construire_dataset_prevision(historique: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque jour J, ne garde que l'information connue à 14h J
    et la cible = les 24 heures de J+1 (aucune fuite de données)."""
    raise NotImplementedError


def decoupage_temporel(dataset: pd.DataFrame):
    """Train / validation / test chronologiques."""
    raise NotImplementedError
