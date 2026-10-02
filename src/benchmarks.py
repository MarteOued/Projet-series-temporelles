"""Modèles de référence et modèle simple (responsable : Martino)."""
import pandas as pd


def benchmark_semaine_precedente(conso: pd.Series, jour) -> pd.Series:
    """Même jour de la semaine, semaine précédente (24 valeurs)."""
    raise NotImplementedError


def benchmark_moyenne_jours_comparables(conso: pd.Series, jour, n: int = 4) -> pd.Series:
    """Moyenne des n derniers jours comparables connus à 14h J."""
    raise NotImplementedError


def modele_simple(X_train, y_train):
    """Régression calendrier + historiques de consommation."""
    raise NotImplementedError
