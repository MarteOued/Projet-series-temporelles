"""Prépare les fichiers lus par le tableau de bord (app/tableau_de_bord.py).

Utilisation
-----------
    python -m src.visualisation

Le tableau de bord ne recalcule aucun modèle : il lit deux fichiers compacts, écrits
ici à partir des résultats déjà produits (src/experiences.py, src/analyses.py,
src/comparaison.py, src/test_bonus.py). Ils sont versionnés avec data/resultats/,
pour que le tableau de bord marche dès qu'on clone le dépôt.

1. visualisation_previsions.csv : une ligne par période, jour cible et heure, avec la
   vraie consommation et la prévision de chaque méthode. Seulement les jours où TOUTES
   les méthodes ont leurs 24 heures (les mêmes jours que dans les comparaisons).
2. visualisation_jours.csv : une ligne par jour de 2016 à mi-2026 (consommation
   moyenne et maximale, température moyenne réelle, type de jour).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import analyses, comparaison, config, evaluation, features, rte, test_bonus

DOSSIER_RESULTATS = comparaison.DOSSIER_RESULTATS
FICHIER_PREVISIONS = DOSSIER_RESULTATS / "visualisation_previsions.csv"
FICHIER_JOURS = DOSSIER_RESULTATS / "visualisation_jours.csv"

# Noms courts des méthodes, dans l'ordre d'affichage
NOMS_COURTS = {
    "B0 : veille effective": "B0",
    "B1 : semaine précédente": "B1",
    "B2 : moyenne de 4 semaines": "B2",
    "M1 : calendrier + retards": "M1",
    "M2 : M1 + température": "M2",
    "M3 : gradient boosting": "M3",
    "M4 : M1 + ARMA": "M4",
    "Plafond : M2 + météo parfaite": "Plafond",
}
METHODES = list(NOMS_COURTS.values())

PERIODES = {
    "validation": "Validation 2023",
    "test": "Test 2024-2025",
    "test_bonus": "Test bonus 2026",
}


# ===========================================================================
# 1. Toutes les prévisions, mêmes jours
# ===========================================================================

def previsions_bonus(conso_h):
    """Vraies valeurs et prévisions (jour x heure) du test bonus 2026."""
    reel, previsions = test_bonus.benchmarks_bonus(conso_h)
    noms = {code: nom for nom, code in comparaison.MODELES.items()}
    for code in comparaison.MODELES.values():
        fichier = DOSSIER_RESULTATS / f"predictions_test_bonus_{code}_2026.csv"
        previsions[noms[code]] = comparaison.tableau_jour_heure(pd.read_csv(fichier))
    return reel, previsions


def en_lignes(nom_periode, reel, previsions):
    """Passe des tableaux jour x heure à une ligne par (jour, heure), jours communs seulement."""
    jours = evaluation.jours_comparables(reel, *previsions.values())
    colonnes = {"reel_MW": reel.loc[jours]}
    colonnes.update({NOMS_COURTS[nom]: p.loc[jours] for nom, p in previsions.items()})
    morceaux = []
    for nom, tableau in colonnes.items():
        serie = tableau.stack()
        serie.name = nom
        morceaux.append(serie)
    lignes = pd.concat(morceaux, axis=1).rename_axis(["jour_cible", "heure"]).reset_index()
    lignes.insert(0, "periode", nom_periode)
    lignes["jour_cible"] = pd.to_datetime(lignes["jour_cible"]).dt.strftime("%Y-%m-%d")
    return lignes[["periode", "jour_cible", "heure", "reel_MW"] + METHODES]


def toutes_les_previsions(conso_h=None):
    conso_h = rte.lire_prepare() if conso_h is None else conso_h
    morceaux = []
    for nom_periode in ("validation", "test"):
        _, reel, previsions = comparaison.comparer_periode(nom_periode, test_final=True, conso_h=conso_h)
        morceaux.append(en_lignes(nom_periode, reel, previsions))
    morceaux.append(en_lignes("test_bonus", *previsions_bonus(conso_h)))
    return pd.concat(morceaux, ignore_index=True)


# ===========================================================================
# 2. Un résumé par jour sur dix ans
# ===========================================================================

def resume_des_jours(conso_h=None):
    conso_h = rte.lire_prepare() if conso_h is None else conso_h
    debut, fin = config.DECOUPAGE["apprentissage"][0], config.TEST_BONUS[1]
    jours = pd.date_range(debut, fin, freq="D")

    conso = conso_h["consommation_MW"]
    jour_paris = conso.index.tz_convert(config.FUSEAU).tz_localize(None).normalize()
    par_jour = conso.groupby(jour_paris).agg(["mean", "max"]).reindex(jours)

    description = analyses.description_des_jours(jours)
    resume = pd.DataFrame({
        "jour": jours.strftime("%Y-%m-%d"),
        "conso_moyenne_MW": par_jour["mean"].to_numpy(),
        "conso_max_MW": par_jour["max"].to_numpy(),
        "temperature_C": description["temperature_C"].to_numpy(),
        "type_jour": description["type_jour"].to_numpy(),
        "saison": description["saison"].to_numpy(),
        "jour_semaine": jours.dayofweek,
        "periode": [features.periode_jour_cible(j) for j in jours],
    })
    return resume


# ===========================================================================
# Outils pour le tableau de bord (testés, mêmes calculs que le rapport)
# ===========================================================================

def tableau_jour_heure(previsions, colonne):
    """Une ligne par jour, 24 colonnes (heures de Paris), pour une méthode ou le réel."""
    tableau = previsions.pivot(index="jour_cible", columns="heure", values=colonne)
    tableau.index = pd.to_datetime(tableau.index)
    tableau.columns = [int(h) for h in tableau.columns]
    return tableau.reindex(columns=evaluation.HEURES)


def erreurs_quotidiennes(previsions, methode):
    """Erreurs de chaque jour pour une méthode (evaluation.erreurs_par_jour)."""
    return evaluation.erreurs_par_jour(
        tableau_jour_heure(previsions, "reel_MW"), tableau_jour_heure(previsions, methode)
    )


def scores(previsions, methodes=METHODES):
    """Tableau des scores (evaluation.resumer) : une ligne par méthode."""
    return pd.DataFrame({m: evaluation.resumer(erreurs_quotidiennes(previsions, m)) for m in methodes}).T


def main():
    conso_h = rte.lire_prepare()
    previsions = toutes_les_previsions(conso_h)
    previsions.to_csv(FICHIER_PREVISIONS, index=False, float_format="%.1f")
    print(f"  -> {FICHIER_PREVISIONS.relative_to(config.RACINE)} ({len(previsions)} lignes)")
    jours = resume_des_jours(conso_h)
    jours.to_csv(FICHIER_JOURS, index=False, float_format="%.2f")
    print(f"  -> {FICHIER_JOURS.relative_to(config.RACINE)} ({len(jours)} lignes)")
    for nom_periode, titre in PERIODES.items():
        partie = previsions[previsions["periode"] == nom_periode]
        print(f"{titre} : {partie['jour_cible'].nunique()} jours ; MAE (MW) :",
              scores(partie)["MAE (MW)"].round(0).to_dict())


if __name__ == "__main__":
    main()
