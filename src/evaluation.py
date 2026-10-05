"""Mesures d'erreur des prévisions : la même règle pour toutes les méthodes.

Une prévision porte sur un jour cible (J+1) et ses 24 heures. Les tableaux comparés ont
donc la même forme : une ligne par jour cible (date de Paris), une colonne par heure de
Paris (0 à 23), des valeurs en MW.

Mesures calculées pour chaque jour (le sujet demande plusieurs critères complémentaires) :
- mae            : erreur absolue moyenne sur les 24 heures (MW) ;
- rmse           : racine de l'erreur quadratique moyenne sur les 24 heures (MW) ;
- mape           : erreur absolue moyenne en pourcentage de la vraie valeur (%) ;
- biais          : erreur moyenne avec son signe (MW). Positif = on prévoit trop ;
- erreur_energie : erreur sur la consommation totale du jour (MWh). Chaque valeur horaire
                   est une puissance moyenne sur 1 heure, donc la somme des 24 valeurs
                   donne l'énergie du jour en MWh ;
- erreur_pointe  : erreur sur la valeur maximale du jour (MW) ;
- ecart_heure_pointe : écart, en heures, entre l'heure de la pointe prévue et la vraie.
"""
import numpy as np
import pandas as pd

HEURES = list(range(24))


def jours_comparables(reel, *previsions):
    """Jours où la vraie valeur ET toutes les prévisions ont leurs 24 heures.

    Le sujet demande de comparer les méthodes sur les mêmes dates : on ne garde donc
    que les jours complets pour tout le monde.
    """
    complet = reel[HEURES].notna().all(axis=1)
    for prevision in previsions:
        complet &= prevision.reindex(reel.index)[HEURES].notna().all(axis=1)
    return reel.index[complet]


def erreurs_par_jour(reel, prevu):
    """Calcule les mesures d'erreur pour chaque jour cible présent dans les deux tableaux."""
    jours = reel.index.intersection(prevu.index)
    r = reel.loc[jours, HEURES].to_numpy(dtype=float)
    p = prevu.loc[jours, HEURES].to_numpy(dtype=float)
    ecart = p - r  # positif = on prévoit trop

    return pd.DataFrame({
        "mae": np.abs(ecart).mean(axis=1),
        "rmse": np.sqrt((ecart ** 2).mean(axis=1)),
        "mape": (np.abs(ecart) / r).mean(axis=1) * 100,
        "biais": ecart.mean(axis=1),
        "erreur_energie": p.sum(axis=1) - r.sum(axis=1),
        "erreur_pointe": p.max(axis=1) - r.max(axis=1),
        "ecart_heure_pointe": np.abs(p.argmax(axis=1) - r.argmax(axis=1)),
    }, index=jours)


def resumer(erreurs):
    """Résume les erreurs quotidiennes en un score par mesure.

    Le RMSE global se calcule à partir des carrés (et non comme moyenne des RMSE
    quotidiens) : c'est la racine de la moyenne de toutes les erreurs au carré.
    """
    return pd.Series({
        "nb_jours": len(erreurs),
        "MAE (MW)": erreurs["mae"].mean(),
        "RMSE (MW)": np.sqrt((erreurs["rmse"] ** 2).mean()),
        "MAPE (%)": erreurs["mape"].mean(),
        "biais (MW)": erreurs["biais"].mean(),
        "erreur énergie du jour (GWh, absolue)": erreurs["erreur_energie"].abs().mean() / 1000,
        "erreur pointe (MW, absolue)": erreurs["erreur_pointe"].abs().mean(),
        "écart heure de pointe (h)": erreurs["ecart_heure_pointe"].mean(),
        "heure de pointe exacte (% des jours)": (erreurs["ecart_heure_pointe"] == 0).mean() * 100,
    })


def comparer(reel, previsions):
    """Tableau de comparaison : une colonne par méthode, sur les mêmes jours pour toutes.

    previsions : dict {nom de la méthode: tableau jour x heure}.
    """
    jours = jours_comparables(reel, *previsions.values())
    return pd.DataFrame({
        nom: resumer(erreurs_par_jour(reel.loc[jours], prevision.loc[jours]))
        for nom, prevision in previsions.items()
    })
