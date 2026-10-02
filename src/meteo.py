"""Données météo SYNOP Météo-France (responsable : binôme)."""
import pandas as pd


def charger_synop(chemin) -> pd.DataFrame:
    raise NotImplementedError


def selectionner_stations(df: pd.DataFrame) -> pd.DataFrame:
    """Garde les stations représentatives de la France métropolitaine."""
    raise NotImplementedError


def agreger_meteo_horaire(df: pd.DataFrame) -> pd.DataFrame:
    """Agrégation spatiale + passage au pas horaire."""
    raise NotImplementedError
