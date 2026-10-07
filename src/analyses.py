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
   le retrait du confinement, sur la validation 2023.
3. Erreurs de toutes les méthodes (mêmes jours) par saison, type de jour,
   température, heure, et biais par mois.
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
    return pd.DataFrame({
        "saison": jours.month.map(SAISONS),
        "type_jour": type_jour,
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
        for critere in ("saison", "type_jour", "classe_temperature", "mois"):
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

    periodes = [("validation", "2023")] + ([("test", "2024_2025")] if args.test_final else [])
    conso_h = rte.lire_prepare()
    for nom_periode, suffixe in periodes:
        print(f"Plafond « météo parfaite » ({nom_periode})")
        fichier = comparaison.FICHIERS_PREDICTIONS[nom_periode].format("plafond")
        _sauver(plafond_meteo_parfaite(donnees, nom_periode), fichier.removesuffix(".csv"))

        print(f"Erreurs détaillées et pires jours ({nom_periode})")
        _, reel, previsions = comparaison.comparer_periode(nom_periode, args.test_final, conso_h)
        _sauver(erreurs_par_groupe(reel, previsions), f"erreurs_par_groupe_{suffixe}")
        _sauver(pires_jours(reel, previsions), f"pires_jours_m2_{suffixe}")


if __name__ == "__main__":
    main()
