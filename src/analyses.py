"""Analyses demandées par l'énoncé, une fois les modèles choisis sur 2023.

Utilisation
-----------
    python -m src.analyses                  # validation 2023 seulement
    python -m src.analyses --test-final     # + test 2024-2025 (choix déjà gelés)

Ce que je calcule
-----------------
1. Plafond « météo parfaite » : M2 retenu + la VRAIE température du jour cible.
   Ce n'est pas une prévision possible à 14 h : il montre seulement combien on
   gagnerait avec une prévision météo parfaite. Il n'entre dans aucun choix.
2. Décision 14 : un seul modèle linéaire pour les 24 heures contre 24 modèles
   (un par heure), sur la validation 2023. Décision 9 : M1 et M2 avec et sans
   le retrait du confinement, sur la validation 2023. Diagnostic de M4.
3. Erreurs de toutes les méthodes (mêmes jours) par saison, trimestre, type de
   jour, férié en semaine ou le week-end, température, heure, et biais par mois.
   Test de Diebold-Mariano : M2 contre chaque autre méthode.
4. Les 3 pires jours de M2, avec ce qui s'est passé ces jours-là.

Toutes les prévisions suivent le protocole des modèles : 4 blocs trimestriels
en 2023, réestimation mensuelle sur 2024-2025, apprentissage strictement
antérieur au bloc prévu, Covid exclu (modeles_lineaires.apprentissage_avant).
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src import comparaison, config, evaluation, features, rte
from src import modeles_lineaires as m1
from src import modeles_meteo as m2

DOSSIER_RESULTATS = comparaison.DOSSIER_RESULTATS

# Configuration de M2 retenue sur 2023 (data/resultats/ablation_m2_2023.csv)
CANDIDAT_M2 = "temp_38_ponderee"
VARIANTE_M2 = "M2-F"

SEUIL_CHAUFFAGE = features.SEUIL_CHAUFFAGE_C
SEUIL_CLIMATISATION = features.SEUIL_CLIMATISATION_C

VARIABLES_PLAFOND = [
    "temp_parfaite_heure",          # température réelle à l'heure cible
    "temp_parfaite_jour",           # moyenne réelle du jour cible
    "degres_chauffage_parfaits",    # max(0, 15 - moyenne réelle du jour cible)
    "degres_climatisation_parfaits",
]


# ===========================================================================
# Outil commun : prévoir bloc par bloc, comme les modèles du projet
# ===========================================================================

def predire_par_blocs(donnees, nom_periode, ajuster, predire):
    """Ajuste avant chaque bloc (données strictement antérieures) et prévoit le bloc.

    nom_periode : "validation" (4 trimestres de 2023) ou "test" (24 mois de 2024-2025).
    ajuster(apprentissage) -> modèle ; predire(modele, bloc) -> prévisions en MW.
    """
    if nom_periode == "validation":
        blocs = m1.BLOCS_VALIDATION_2023
        autorisees = m1.PERIODES_AUTORISEES_VALIDATION_EXPANDING
    else:
        blocs = m1.blocs_mensuels_test_final()
        autorisees = m1.PERIODES_AUTORISEES_TEST_FINAL

    jours = pd.to_datetime(donnees[m1.COLONNE_JOUR]).dt.normalize()
    morceaux = []
    for nom_bloc, debut, fin in blocs:
        apprentissage = m1.apprentissage_avant(donnees, debut, periodes_autorisees=autorisees)
        bloc = donnees.loc[
            (donnees[m1.COLONNE_PERIODE] == nom_periode) & (jours >= debut) & (jours < fin)
        ].copy()
        modele = ajuster(apprentissage)
        bloc["prediction_MW"] = predire(modele, bloc)
        bloc["bloc"] = nom_bloc
        morceaux.append(bloc[[m1.COLONNE_JOUR, m1.COLONNE_HEURE, m1.COLONNE_CIBLE,
                              "prediction_MW", "bloc"]])
    return (pd.concat(morceaux, ignore_index=True)
            .sort_values([m1.COLONNE_JOUR, m1.COLONNE_HEURE]).reset_index(drop=True))


def _pipeline_lineaire(categorielles, categories, numeriques):
    return Pipeline([
        ("preparation", ColumnTransformer(
            [("categoriel", OneHotEncoder(categories=categories, drop="first",
                                          handle_unknown="ignore", sparse_output=False),
              categorielles),
             ("numerique", "passthrough", numeriques)],
            remainder="drop",
        )),
        ("regression", LinearRegression()),
    ])


def ajuster_par_heure(variables_numeriques):
    """Renvoie (ajuster, predire) pour 24 régressions linéaires, une par heure cible."""
    categorielles = list(m1.VARIABLES_CATEGORIELLES_M1)
    categories = [list(range(7)), list(range(1, 13))]

    def ajuster(apprentissage):
        modeles = {}
        for heure, groupe in apprentissage.groupby(m1.COLONNE_HEURE):
            modele = _pipeline_lineaire(categorielles, categories, variables_numeriques(heure))
            modeles[heure] = modele.fit(groupe, groupe[m1.COLONNE_CIBLE])
        return modeles

    def predire(modeles, bloc):
        prevision = pd.Series(np.nan, index=bloc.index)
        for heure, groupe in bloc.groupby(m1.COLONNE_HEURE):
            prevision.loc[groupe.index] = modeles[heure].predict(groupe)
        return prevision.to_numpy()

    return ajuster, predire


# ===========================================================================
# 1. Plafond « météo parfaite »
# ===========================================================================

def ajouter_meteo_parfaite(donnees, candidat=CANDIDAT_M2):
    """Ajoute la vraie température du jour cible (version interpolée « météo parfaite »)."""
    colonne = f"{candidat}_meteo_parfaite"
    meteo = pd.read_csv(features.FICHIER_TEMPERATURES, index_col="date_heure_utc",
                        parse_dates=["date_heure_utc"])[colonne]
    # La version interpolée s'arrête à la dernière observation (31/12/2025 21 h UTC) :
    # pour les 2 dernières heures de la série, je garde cette dernière valeur.
    meteo = meteo.ffill(limit=3)
    jour_paris = meteo.index.tz_convert(config.FUSEAU).tz_localize(None).normalize()
    moyenne_jour = meteo.groupby(jour_paris).mean()

    resultat = donnees.copy()
    instants = pd.to_datetime(resultat["date_heure_cible_utc"], utc=True)
    resultat["temp_parfaite_heure"] = meteo.reindex(instants).to_numpy()
    resultat["temp_parfaite_jour"] = moyenne_jour.reindex(
        pd.to_datetime(resultat[m1.COLONNE_JOUR])).to_numpy()
    resultat["degres_chauffage_parfaits"] = (SEUIL_CHAUFFAGE - resultat["temp_parfaite_jour"]).clip(lower=0)
    resultat["degres_climatisation_parfaits"] = (resultat["temp_parfaite_jour"] - SEUIL_CLIMATISATION).clip(lower=0)
    if resultat[VARIABLES_PLAFOND].isna().any().any():
        raise ValueError("Température « météo parfaite » manquante pour certains jours cibles.")
    return resultat


def plafond_meteo_parfaite(donnees, nom_periode):
    donnees = ajouter_meteo_parfaite(donnees)
    variables = lambda heure: (
        m2.variables_numeriques_m2(heure, CANDIDAT_M2, VARIANTE_M2) + VARIABLES_PLAFOND
    )
    return predire_par_blocs(donnees, nom_periode, *ajuster_par_heure(variables))


# ===========================================================================
# 2. Décision 14 : un seul modèle contre 24
# ===========================================================================

VARIABLES_UN_MODELE = [
    "conso_veille_effective_MW",   # 24 h avant si H <= 12, sinon 48 h avant
    "veille_a_48h",                # 1 si la valeur précédente date de 48 h
    "conso_lag48_MW",
    "conso_lag168_MW",
] + list(m1.VARIABLES_CALENDRIER_BINAIRES_M1)


def un_seul_modele_m1(donnees, nom_periode="validation"):
    """M1 en un seul modèle : l'heure cible devient une variable (24 catégories)."""
    donnees = donnees.assign(veille_a_48h=(donnees["retard_effectif_h"] == 48).astype(int))
    categorielles = list(m1.VARIABLES_CATEGORIELLES_M1) + [m1.COLONNE_HEURE]
    categories = [list(range(7)), list(range(1, 13)), list(range(24))]

    def ajuster(apprentissage):
        modele = _pipeline_lineaire(categorielles, categories, VARIABLES_UN_MODELE)
        return modele.fit(apprentissage, apprentissage[m1.COLONNE_CIBLE])

    return predire_par_blocs(donnees, nom_periode, ajuster, lambda modele, bloc: modele.predict(bloc))


def decision_14(donnees):
    vingt_quatre = m1.valider_m1_expanding(donnees)
    un_seul = un_seul_modele_m1(donnees)
    lignes = []
    for nom, predictions in (("24 modèles (un par heure)", vingt_quatre.predictions),
                             ("1 modèle (heure en variable)", un_seul)):
        metriques = m1.calculer_metriques(predictions)
        metriques.update(m1.calculer_metriques_journalieres(predictions))
        lignes.append({"forme": nom, **metriques})
    return pd.DataFrame(lignes)


def sensibilite_covid(donnees):
    """Décision 9 : M1 et M2 retenus, avec et sans le retrait du confinement (2023)."""
    lignes = []
    for exclusion in (True, False):
        version = donnees if exclusion else donnees.assign(**{m1.COLONNE_COVID: False})
        for nom, resultat in (
            ("M1", m1.valider_m1_expanding(version)),
            ("M2", m2.valider_m2_expanding(version, CANDIDAT_M2, VARIANTE_M2)),
        ):
            lignes.append({
                "modele": nom,
                "confinement_retire": exclusion,
                **{cle: resultat.metriques[cle] for cle in ("MAE_MW", "RMSE_MW", "MAE_pointe_MW")},
            })
    return pd.DataFrame(lignes)


def diagnostic_m4(donnees):
    """Pourquoi M4 n'aide pas : les erreurs de M1 se répètent-elles d'un jour à l'autre ?

    M4 corrige la prévision avec l'erreur de M1 de la veille (H <= 12) ou de l'avant-veille
    (H >= 13). Ça ne marche que si ces erreurs se ressemblent d'un jour à l'autre, à la même
    heure. Je mesure cette ressemblance (autocorrélation) à 1 et 2 jours, sur les erreurs
    vues par M4 pendant l'apprentissage (2016-2022) et sur les vraies erreurs de 2023.
    """
    apprentissage = m1.apprentissage_avant(donnees, m1.BLOCS_VALIDATION_2023[0][1])
    dans = m1.predire_m1(m1.ajuster_modeles_m1(apprentissage), apprentissage)
    hors = m1.valider_m1_expanding(donnees).predictions
    lignes = []
    for nom, predictions in (("apprentissage 2016-2022 (ce que voit M4)", dans),
                             ("validation 2023 (erreurs réelles)", hors)):
        p = predictions.assign(
            erreur=predictions[m1.COLONNE_CIBLE] - predictions["prediction_MW"]
        ).sort_values([m1.COLONNE_HEURE, m1.COLONNE_JOUR])
        par_heure = p.groupby(m1.COLONNE_HEURE)["erreur"]
        lignes.append({
            "erreurs_de_M1": nom,
            "moyenne_MW": p["erreur"].mean(),
            "ecart_type_MW": p["erreur"].std(),
            "autocorrelation_1_jour": par_heure.apply(lambda e: e.autocorr(1)).mean(),
            "autocorrelation_2_jours": par_heure.apply(lambda e: e.autocorr(2)).mean(),
        })
    return pd.DataFrame(lignes)


# ===========================================================================
# 3. Erreurs par groupe de jours (mêmes jours pour toutes les méthodes)
# ===========================================================================

SAISONS = {12: "hiver", 1: "hiver", 2: "hiver", 3: "printemps", 4: "printemps", 5: "printemps",
           6: "été", 7: "été", 8: "été", 9: "automne", 10: "automne", 11: "automne"}


def description_des_jours(jours):
    """Saison, type de jour et température réelle moyenne de chaque jour cible."""
    calendrier = pd.read_csv(features.FICHIER_CALENDRIER, index_col="date", parse_dates=["date"])
    calendrier = calendrier.reindex(jours)
    meteo = pd.read_csv(features.FICHIER_TEMPERATURES, index_col="date_heure_utc",
                        parse_dates=["date_heure_utc"])[f"{CANDIDAT_M2}_meteo_parfaite"]
    temperature = meteo.groupby(meteo.index.tz_convert(config.FUSEAU).tz_localize(None).normalize()).mean()

    type_jour = np.select(
        [calendrier["ferie"] == 1, calendrier["pont_potentiel"] == 1,
         calendrier["periode_noel"] == 1, calendrier["weekend"] == 1],
        ["férié", "pont", "Noël", "week-end"], default="ouvré",
    )
    t = temperature.reindex(jours)
    ferie_selon_jour = np.select(
        [(calendrier["ferie"] == 1) & (calendrier["weekend"] == 1), calendrier["ferie"] == 1],
        ["férié le week-end", "férié en semaine"], default="non férié",
    )
    return pd.DataFrame({
        "saison": jours.month.map(SAISONS),
        "trimestre": [f"{j.year}-T{(j.month - 1) // 3 + 1}" for j in jours],
        "type_jour": type_jour,
        "ferie_selon_jour": ferie_selon_jour,
        "temperature_C": t.to_numpy(),
        "classe_temperature": pd.cut(t, [-np.inf, 5, 10, 15, 20, np.inf],
                                     labels=["< 5 °C", "5-10 °C", "10-15 °C", "15-20 °C", "> 20 °C"]).astype(str),
        "mois": jours.strftime("%Y-%m"),
    }, index=jours)


def erreurs_par_groupe(reel, previsions):
    """Une ligne par (méthode, critère, groupe) : nombre de jours, MAE, biais."""
    jours = evaluation.jours_comparables(reel, *previsions.values())
    description = description_des_jours(jours)
    lignes = []
    for nom, prevision in previsions.items():
        erreurs = evaluation.erreurs_par_jour(reel.loc[jours], prevision.loc[jours]).join(description)
        for critere in ("saison", "trimestre", "type_jour", "ferie_selon_jour",
                        "classe_temperature", "mois"):
            for groupe, sous in erreurs.groupby(critere):
                lignes.append({"methode": nom, "critere": critere, "groupe": groupe,
                               "nb_jours": len(sous), "MAE_MW": sous["mae"].mean(),
                               "biais_MW": sous["biais"].mean()})
        ecart = prevision.loc[jours] - reel.loc[jours]
        for heure in ecart.columns:
            lignes.append({"methode": nom, "critere": "heure", "groupe": heure,
                           "nb_jours": len(jours), "MAE_MW": ecart[heure].abs().mean(),
                           "biais_MW": ecart[heure].mean()})
    return pd.DataFrame(lignes)


# ===========================================================================
# 3 bis. L'écart entre deux méthodes est-il significatif ?
# ===========================================================================

def significativite(reel, previsions, reference="M2 : M1 + température"):
    """Test de Diebold-Mariano entre la référence et chaque autre méthode, mêmes jours.

    Deux pertes par jour : l'erreur absolue moyenne (MAE) et l'erreur quadratique moyenne
    (qui donne le RMSE). Une p-valeur > 0,05 veut dire : écart compatible avec le hasard.
    """
    jours = evaluation.jours_comparables(reel, *previsions.values())
    erreurs = {nom: evaluation.erreurs_par_jour(reel.loc[jours], p.loc[jours])
               for nom, p in previsions.items()}
    lignes = []
    for autre in previsions:
        if autre == reference:
            continue
        for perte, colonne, carre in (("MAE", "mae", False), ("RMSE", "rmse", True)):
            a, b = erreurs[reference][colonne], erreurs[autre][colonne]
            if carre:
                a, b = a ** 2, b ** 2
            test = evaluation.diebold_mariano(a, b)
            lignes.append({
                "reference": reference, "autre_methode": autre, "perte": perte,
                "ecart_moyen": test["ecart_moyen"], "z": test["z"], "p_valeur": test["p_valeur"],
                "part_jours_reference_meilleure": test["part_jours_A_meilleure"],
                "conclusion": ("écart non significatif" if test["p_valeur"] > 0.05
                               else "référence meilleure" if test["ecart_moyen"] < 0
                               else "autre méthode meilleure"),
            })
    return pd.DataFrame(lignes)


# ===========================================================================
# 4. Les 3 pires jours de M2
# ===========================================================================

def pires_jours(reel, previsions, modele="M2 : M1 + température", nombre=3):
    jours = evaluation.jours_comparables(reel, *previsions.values())
    erreurs = evaluation.erreurs_par_jour(reel.loc[jours], previsions[modele].loc[jours])
    pires = erreurs.nlargest(nombre, "mae")
    description = description_des_jours(pires.index)
    veille = description_des_jours(pires.index - pd.Timedelta(days=1))
    resultat = pd.DataFrame({
        "jour_cible": pires.index.strftime("%Y-%m-%d"),
        "jour_semaine": pires.index.day_name(locale=None),
        "MAE_MW": pires["mae"].to_numpy(),
        "biais_MW": pires["biais"].to_numpy(),
        "erreur_pointe_MW": pires["erreur_pointe"].to_numpy(),
        "type_jour": description["type_jour"].to_numpy(),
        "temperature_jour_cible_C": description["temperature_C"].to_numpy(),
        "temperature_veille_C": veille["temperature_C"].to_numpy(),
    })
    # Même jour avec d'autres méthodes : le plafond dit si la vraie météo aurait suffi
    for nom in ("B0 : veille effective", "B1 : semaine précédente", "Plafond : M2 + météo parfaite"):
        resultat[f"MAE_{nom.split(' :')[0]}_MW"] = evaluation.erreurs_par_jour(
            reel.loc[pires.index], previsions[nom].loc[pires.index])["mae"].to_numpy()
    return resultat


# ===========================================================================
# Lancement
# ===========================================================================

def _sauver(tableau, nom):
    chemin = DOSSIER_RESULTATS / f"{nom}.csv"
    tableau.to_csv(chemin, index=False)
    print(f"  -> {chemin.relative_to(config.RACINE)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test-final", action="store_true",
                        help="analyse aussi le test 2024-2025 (choix déjà gelés)")
    args = parser.parse_args(argv)

    donnees = pd.read_csv(features.FICHIER_DATASET)

    print("Décision 14 : un seul modèle contre 24 (2023)")
    _sauver(decision_14(donnees), "decision14_un_modele_contre_24_2023")

    print("Décision 9 : sensibilité au retrait du confinement (2023)")
    _sauver(sensibilite_covid(donnees), "sensibilite_covid_2023")

    print("Diagnostic de M4 : les erreurs de M1 se répètent-elles ? (2023)")
    _sauver(diagnostic_m4(donnees), "diagnostic_m4_2023")

    periodes = [("validation", "2023")] + ([("test", "2024_2025")] if args.test_final else [])
    conso_h = rte.lire_prepare()
    for nom_periode, suffixe in periodes:
        print(f"Plafond « météo parfaite » ({nom_periode})")
        fichier = comparaison.FICHIERS_PREDICTIONS[nom_periode].format("plafond")
        _sauver(plafond_meteo_parfaite(donnees, nom_periode), fichier.removesuffix(".csv"))

        print(f"Erreurs détaillées et pires jours ({nom_periode})")
        _, reel, previsions = comparaison.comparer_periode(nom_periode, args.test_final, conso_h)
        _sauver(erreurs_par_groupe(reel, previsions), f"erreurs_par_groupe_{suffixe}")
        _sauver(significativite(reel, previsions), f"significativite_{suffixe}")
        _sauver(pires_jours(reel, previsions), f"pires_jours_m2_{suffixe}")


if __name__ == "__main__":
    main()
