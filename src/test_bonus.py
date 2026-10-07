"""Test bonus : janvier à juin 2026 (décision 3).

Utilisation
-----------
    python -m src.test_bonus

Règles
------
- Utilisé UNE SEULE FOIS, après le test final 2024-2025. Il ne sert à choisir ou
  régler RIEN : chaque modèle garde exactement sa configuration gelée (M1 ; M2 avec
  temp_38_ponderee et M2-F ; M3-1 ; M4 = M1 + AR(1) ; plafond = M2 + météo parfaite).
- Même protocole que le test final : réestimation au début de chaque mois, avec
  toutes les données dont le jour cible est strictement antérieur au mois prévu
  (2016-2025 et les mois de 2026 déjà passés), Covid exclu de l'apprentissage.
- Toutes les méthodes (B0, B1, B2, M1 à M4, plafond) sont notées sur les mêmes jours.

Limites à présenter avec les résultats : 6 mois seulement (surtout hiver et
printemps), données 2026 consolidées que RTE peut encore corriger.
"""

from __future__ import annotations

import pandas as pd

from src import analyses, benchmarks, comparaison, config, evaluation, features, rte
from src import evaluation_finale_m4 as e4
from src import modeles_arma as m4
from src import modeles_hgbr as m3
from src import modeles_lineaires as m1
from src import modeles_meteo as m2

FICHIER_DATASET_BONUS = config.DATA_PREPAREES / "dataset_test_bonus_2026.csv"
DOSSIER_RESULTATS = comparaison.DOSSIER_RESULTATS

PERIODES_AUTORISEES = {"apprentissage", "validation", "test", "test_bonus"}


def blocs_mensuels():
    """Les 6 mois du test bonus : (nom, premier jour, premier jour du mois suivant)."""
    debut, fin = (pd.Timestamp(d) for d in config.TEST_BONUS)
    mois = pd.date_range(debut, fin, freq="MS")
    return [(m.strftime("%Y-%m"), m, m + pd.offsets.MonthBegin(1)) for m in mois]


def construire_dataset_bonus():
    """Variables à 14 h des jours cibles de 2026 (même code que pour 2016-2025)."""
    consommation, meteo, calendrier = features.charger_entrees()
    debut, fin = config.TEST_BONUS
    dataset = features.construire_dataset(consommation, meteo, calendrier, debut, fin)
    if not (dataset["periode"] == "test_bonus").all():
        raise ValueError("Des jours du test bonus ne sont pas étiquetés « test_bonus ».")
    dataset.to_csv(FICHIER_DATASET_BONUS, index=False)
    print(f"  -> {FICHIER_DATASET_BONUS.relative_to(config.RACINE)} ({len(dataset)} lignes)")
    return dataset


def predire_par_mois(donnees, ajuster, predire):
    """Réestime avant chaque mois de 2026 et prévoit ce mois."""
    jours = pd.to_datetime(donnees[m1.COLONNE_JOUR]).dt.normalize()
    morceaux = []
    for nom_bloc, debut, fin in blocs_mensuels():
        apprentissage = m1.apprentissage_avant(donnees, debut, periodes_autorisees=PERIODES_AUTORISEES)
        if pd.to_datetime(apprentissage[m1.COLONNE_JOUR]).max() >= debut:
            raise RuntimeError(f"Fuite : l'apprentissage du bloc {nom_bloc} contient le bloc.")
        bloc = donnees.loc[
            (donnees[m1.COLONNE_PERIODE] == "test_bonus") & (jours >= debut) & (jours < fin)
        ].copy()
        predictions = predire(ajuster(apprentissage), bloc)
        if isinstance(predictions, pd.DataFrame):
            # Certains modèles (M4) renvoient le jour en date, d'autres en texte : je les aligne
            predictions = predictions[[m1.COLONNE_JOUR, m1.COLONNE_HEURE, "prediction_MW"]].assign(
                **{m1.COLONNE_JOUR: lambda d: pd.to_datetime(d[m1.COLONNE_JOUR]).dt.strftime("%Y-%m-%d")}
            )
            bloc = bloc.assign(
                **{m1.COLONNE_JOUR: pd.to_datetime(bloc[m1.COLONNE_JOUR]).dt.strftime("%Y-%m-%d")}
            ).merge(predictions, on=[m1.COLONNE_JOUR, m1.COLONNE_HEURE], how="left")
        else:
            bloc["prediction_MW"] = predictions
        bloc["bloc"] = nom_bloc
        morceaux.append(bloc[[m1.COLONNE_JOUR, m1.COLONNE_HEURE, m1.COLONNE_CIBLE,
                              "prediction_MW", "bloc"]])
    resultat = pd.concat(morceaux, ignore_index=True)
    if resultat["prediction_MW"].isna().any():
        raise ValueError("Des prévisions manquent.")
    return resultat.sort_values([m1.COLONNE_JOUR, m1.COLONNE_HEURE]).reset_index(drop=True)


def methodes_gelees():
    """(code, ajuster, predire) pour chaque modèle, avec sa configuration gelée."""
    m3_config = m3.resume_configuration_m3()
    m3_parametres = {cle: m3_config[cle] for cle in
                     ("learning_rate", "max_iter", "max_leaf_nodes", "l2_regularization")}
    candidat, variante = analyses.CANDIDAT_M2, analyses.VARIANTE_M2
    plafond = analyses.ajuster_par_heure(
        lambda heure: m2.variables_numeriques_m2(heure, candidat, variante) + analyses.VARIABLES_PLAFOND
    )
    return [
        ("m1", m1.ajuster_modeles_m1, m1.predire_m1),
        ("m2", lambda a: m2.ajuster_modeles_m2(a, candidat, variante),
         lambda modeles, bloc: m2.predire_m2(modeles, bloc, candidat, variante)),
        ("m3", lambda a: m3.ajuster_modeles_m3(a, **m3_parametres), m3.predire_m3),
        # M4 ajuste M1 puis l'AR(1) dans predire_bloc_m4 : « ajuster » garde l'apprentissage
        ("m4", lambda a: a, lambda a, bloc: m4.predire_bloc_m4(a, bloc, e4.P_FINAL, e4.Q_FINAL)),
        ("plafond", plafond[0], plafond[1]),
    ]


def benchmarks_bonus(conso_h):
    """B0, B1, B2 sur les jours du test bonus (jours de changement d'heure retirés)."""
    conso_jour = benchmarks.consommation_par_jour(conso_h)
    debut, fin = config.TEST_BONUS
    jours = pd.date_range(debut, fin, freq="D")
    jours = jours[~jours.isin(benchmarks.jours_changement_heure(conso_h))]
    for decalages in (benchmarks.DECALAGES_B0, benchmarks.DECALAGE_B1, benchmarks.DECALAGES_B2):
        benchmarks.verifier_disponibilite(jours, decalages)
    previsions = {
        "B0 : veille effective": benchmarks.benchmark_b0(conso_jour, jours),
        "B1 : semaine précédente": benchmarks.benchmark_b1(conso_jour, jours),
        "B2 : moyenne de 4 semaines": benchmarks.benchmark_b2(conso_jour, jours),
    }
    return conso_jour.reindex(jours), previsions


def _sauver(tableau, nom):
    chemin = DOSSIER_RESULTATS / f"{nom}.csv"
    tableau.to_csv(chemin, index=False)
    print(f"  -> {chemin.relative_to(config.RACINE)}")


def main():
    print("Test bonus 2026 : configurations gelées, une seule fois")
    construire_dataset_bonus()
    # Les deux tables sont relues depuis leur fichier : mêmes types de colonnes
    donnees = pd.concat(
        [pd.read_csv(features.FICHIER_DATASET), pd.read_csv(FICHIER_DATASET_BONUS)],
        ignore_index=True,
    )
    donnees_plafond = analyses.ajouter_meteo_parfaite(donnees)

    conso_h = rte.lire_prepare()
    reel, previsions = benchmarks_bonus(conso_h)

    noms = {code: nom for nom, code in comparaison.MODELES.items()}
    for code, ajuster, predire in methodes_gelees():
        print(f"  {code} ...")
        source = donnees_plafond if code == "plafond" else donnees
        predictions = predire_par_mois(source, ajuster, predire)
        _sauver(predictions, f"predictions_test_bonus_{code}_2026")
        cible = comparaison.tableau_jour_heure(predictions, m1.COLONNE_CIBLE)
        jours = cible.index.intersection(reel.index)
        if (cible.loc[jours] - reel.loc[jours]).abs().max().max() > 1e-6:
            raise ValueError(f"{code} : sa cible diffère de la consommation RTE.")
        previsions[noms[code]] = comparaison.tableau_jour_heure(predictions)

    scores = evaluation.comparer(reel, previsions)
    pd.set_option("display.width", 200)
    print(scores.round(1).to_string())
    _sauver(scores.T.rename_axis("methode").reset_index(), "test_bonus_2026_comparaison")
    _sauver(analyses.significativite(reel, previsions), "test_bonus_2026_significativite")
    _sauver(analyses.erreurs_par_groupe(reel, previsions), "test_bonus_2026_erreurs_par_groupe")
    _sauver(analyses.pires_jours(reel, previsions), "test_bonus_2026_pires_jours_m2")


if __name__ == "__main__":
    main()
