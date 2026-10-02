"""Métriques et comparaison des modèles (commun)."""
import numpy as np


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(yhat))))


def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(yhat)) ** 2)))


def erreur_energie_journaliere(y, yhat):
    """Erreur sur le total journalier (24 h)."""
    raise NotImplementedError


def erreur_pic(y, yhat):
    """Erreur sur le pic de consommation de la journée."""
    raise NotImplementedError
