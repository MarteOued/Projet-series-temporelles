"""Benchmark des méthodes d'imputation temporelle des températures SYNOP.

Ce module évalue les méthodes destinées à traiter les valeurs restant
manquantes après l'imputation spatiale, et choisit celle à utiliser pour
chaque longueur de trou.

Principe
--------
Des séquences réellement observées sont artificiellement masquées, pour
plusieurs longueurs de trou (de 1 point = 3 h à 16 points = 48 h). La vérité
terrain est conservée afin de comparer les prédictions.

Seules les observations de la PÉRIODE D'APPRENTISSAGE (antérieures à la fin
de 2022, heure de Paris) sont utilisées : 2023 et le test 2024-2025
n'interviennent jamais dans le choix de la méthode.

Méthodes candidates (CAUSALES : elles n'utilisent que le passé)
------------------------------------------------------------
persistance         : dernière valeur observée avant le trou ;
veille              : même heure la veille ;
persistance_ajustee : dernière valeur + évolution de la veille sur les mêmes
                      heures.
Ces fonctions sont celles de src/imputation_temporelle.py : la méthode testée
est exactement celle qui sera appliquée.

Références NON CAUSALES (interdites dans le pipeline, gardées pour mesurer
le coût de la règle des 14 h)
-------------------------------------------------------------------------
interpolation (non causale) : entre l'observation d'avant et celle d'après ;
journalier ±24 h (non causal) : moyenne de la veille et du lendemain ;
hybride (non causal)          : moyenne des deux précédentes.

Important
---------
Aucune valeur réellement manquante n'est imputée par ce script.
La matrice utilisée comme base est celle obtenue après l'imputation spatiale.
"""

import numpy as np
import pandas as pd

from src import config, protocole
from src.imputation_temporelle import FONCTIONS_METHODES, METHODES_CAUSALES


# =============================================================================
# CONFIGURATION
# =============================================================================

DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

FICHIER_MATRICE = (
    DOSSIER_METEO
    / "temperatures_synop_imputees.csv"
)

FICHIER_SEQUENCES_REELLES = (
    DOSSIER_METEO
    / "sequences_manquantes_residuelles.csv"
)

FICHIER_RESULTATS = (
    DOSSIER_METEO
    / "benchmark_imputation_temporelle.csv"
)

FICHIER_PREDICTIONS = (
    DOSSIER_METEO
    / "predictions_benchmark_temporel.csv"
)

PAS_HEURES = 3

# Longueurs testées (en points de 3 h). Elles couvrent les trous réels (1, 2,
# 3 et 8 points) et au-delà, pour que la règle vaille pour toute longueur.
LONGUEURS = [
    1,
    2,
    3,
    4,
    6,
    8,
    12,
    16,
]

RANDOM_STATE = 42

# Nombre maximal de séquences artificielles par longueur.
#
# Pour les longueurs courtes, 1000 séquences donnent déjà plusieurs milliers
# de températures évaluées tout en gardant un temps d'exécution raisonnable.
NB_SEQUENCES_PAR_LONGUEUR = {
    longueur: 1000
    for longueur in LONGUEURS
}

# Méthodes évaluées : nom (tel qu'écrit dans les résultats) -> colonne.
# Les noms des méthodes causales sont ceux de src/imputation_temporelle.py,
# qui relit ces résultats pour choisir sa méthode.
METHODES = {
    "persistance": "prediction_persistance",
    "veille": "prediction_veille",
    "persistance_ajustee": "prediction_persistance_ajustee",
    "interpolation (non causale)": "prediction_lineaire",
    "journalier ±24 h (non causal)": "prediction_journaliere",
    "hybride (non causal)": "prediction_hybride",
}


# =============================================================================
# LECTURE
# =============================================================================

def lire_matrice():
    """Lit la matrice après l'imputation spatiale."""

    if not FICHIER_MATRICE.exists():
        raise FileNotFoundError(
            "Matrice imputée introuvable : "
            f"{FICHIER_MATRICE}"
        )

    matrice = pd.read_csv(
        FICHIER_MATRICE,
        index_col=0,
        parse_dates=True,
    )

    matrice.index = pd.to_datetime(
        matrice.index,
        utc=True,
    )

    matrice.index.name = "validity_time"

    matrice.columns = [
        str(colonne).zfill(5)
        for colonne in matrice.columns
    ]

    matrice = matrice.sort_index()

    return matrice


def lire_sequences_reelles():
    """Lit le diagnostic des séquences réellement manquantes."""

    if not FICHIER_SEQUENCES_REELLES.exists():
        raise FileNotFoundError(
            "Diagnostic des séquences introuvable : "
            f"{FICHIER_SEQUENCES_REELLES}"
        )

    sequences = pd.read_csv(
        FICHIER_SEQUENCES_REELLES
    )

    sequences["station"] = (
        sequences["station"]
        .astype(str)
        .str.zfill(5)
    )

    sequences["debut"] = pd.to_datetime(
        sequences["debut"],
        utc=True,
    )

    sequences["fin"] = pd.to_datetime(
        sequences["fin"],
        utc=True,
    )

    return sequences


# =============================================================================
# CONTROLE DES LONGUEURS REELLES
# =============================================================================

def afficher_structure_reelle(
    sequences,
):
    """Affiche les longueurs de trous observées dans les vraies données."""

    print()
    print("=" * 90)
    print("STRUCTURE DES TROUS REELS")
    print("=" * 90)

    distribution = (
        sequences["nombre_points"]
        .value_counts()
        .sort_index()
    )

    for longueur, nombre in distribution.items():

        print(
            f"{int(longueur)} point(s) "
            f"= {int(longueur) * PAS_HEURES} h "
            f": {nombre} séquence(s)"
        )

    longueurs_observees = set(
        distribution.index.astype(int)
    )

    longueurs_attendues = set(
        LONGUEURS
    )

    if longueurs_observees != longueurs_attendues:
        print()
        print(
            "ATTENTION : les longueurs observées "
            "diffèrent de la configuration."
        )

        print(
            "Observées :",
            sorted(longueurs_observees),
        )

        print(
            "Configurées :",
            sorted(longueurs_attendues),
        )


# =============================================================================
# CANDIDATS POUR LE BENCHMARK
# =============================================================================

def sequence_est_complete(
    matrice,
    station,
    debut_position,
    longueur,
):
    """Vérifie qu'une séquence et son contexte sont entièrement observés.

    Conditions
    ----------
    - tous les points à masquer sont observés ;
    - le point immédiatement avant est observé ;
    - le point immédiatement après est observé ;
    - les valeurs à J-1 et J+1 de chaque point sont observées.

    - les valeurs à J-1 du point précédant la séquence sont observées
      (nécessaire à la persistance ajustée).

    Ces contraintes permettent d'évaluer toutes les méthodes exactement sur
    les mêmes observations.
    """

    n = len(matrice)

    fin_position = (
        debut_position
        + longueur
        - 1
    )

    position_avant = (
        debut_position - 1
    )

    position_apres = (
        fin_position + 1
    )

    # 24 heures correspondent à 8 observations sur une grille de 3 heures.
    decalage_24h = int(
        24 / PAS_HEURES
    )

    if position_avant < 0:
        return False

    if position_apres >= n:
        return False

    if (
        position_avant - decalage_24h
        < 0
    ):
        return False

    if (
        fin_position + decalage_24h
        >= n
    ):
        return False

    serie = matrice[station]

    # Séquence à cacher.
    valeurs_sequence = serie.iloc[
        debut_position:
        fin_position + 1
    ]

    if valeurs_sequence.isna().any():
        return False

    # Encadrement pour interpolation linéaire.
    if pd.isna(
        serie.iloc[position_avant]
    ):
        return False

    if pd.isna(
        serie.iloc[position_apres]
    ):
        return False

    # Point précédant la séquence, la veille.
    if pd.isna(
        serie.iloc[
            position_avant - decalage_24h
        ]
    ):
        return False

    # Même heure la veille et le lendemain.
    for position in range(
        debut_position,
        fin_position + 1,
    ):

        position_avant_24h = (
            position - decalage_24h
        )

        position_apres_24h = (
            position + decalage_24h
        )

        if pd.isna(
            serie.iloc[
                position_avant_24h
            ]
        ):
            return False

        if pd.isna(
            serie.iloc[
                position_apres_24h
            ]
        ):
            return False

    return True


def construire_candidats(
    matrice,
    longueur,
):
    """Construit toutes les séquences candidates pour une longueur donnée.

    Mêmes conditions que sequence_est_complete, calculées d'un coup pour toute
    la série (version rapide). Seules les séquences dont TOUTES les valeurs
    utilisées (y compris le lendemain des méthodes non causales de référence)
    sont antérieures à la fin de la période d'apprentissage sont retenues.
    """

    decalage_24h = int(
        24 / PAS_HEURES
    )

    # Dernière position utilisable : avant la fin de l'apprentissage
    n_apprentissage = int(
        (matrice.index < protocole.fin_apprentissage_utc()).sum()
    )

    candidats = []

    for station in matrice.columns:

        observe = matrice[station].notna().to_numpy()

        # cumul[i] = nombre de valeurs observées avant la position i
        cumul = np.concatenate([[0], np.cumsum(observe)])

        def bloc_observe(debut, fin):
            """Vrai si toutes les positions de debut à fin (incluses) sont observées."""
            return (cumul[fin + 1] - cumul[debut]) == (fin - debut + 1)

        debuts = np.arange(
            decalage_24h + 1,
            n_apprentissage - longueur - decalage_24h,
        )

        if len(debuts) == 0:
            continue

        valides = (
            # séquence, point avant et point après
            bloc_observe(debuts - 1, debuts + longueur)
            # la veille : de (point avant - 24 h) à (dernier point - 24 h)
            & bloc_observe(debuts - 1 - decalage_24h, debuts + longueur - 1 - decalage_24h)
            # le lendemain (méthodes non causales de référence)
            & bloc_observe(debuts + decalage_24h, debuts + longueur - 1 + decalage_24h)
        )

        candidats.extend(
            (station, int(debut)) for debut in debuts[valides]
        )

    return candidats


# =============================================================================
# ECHANTILLONNAGE
# =============================================================================

def chevauche(
    candidat,
    selection,
    longueur,
):
    """Indique si un candidat chevauche une séquence déjà sélectionnée."""

    station, debut = candidat

    fin = (
        debut
        + longueur
        - 1
    )

    for (
        station_existante,
        debut_existant,
    ) in selection:

        if station != station_existante:
            continue

        fin_existante = (
            debut_existant
            + longueur
            - 1
        )

        if not (
            fin < debut_existant
            or debut > fin_existante
        ):
            return True

    return False


def echantillonner_sequences(
    candidats,
    longueur,
    nombre,
    rng,
):
    """Sélectionne des séquences sans chevauchement pour une même station."""

    if not candidats:
        return []

    ordre = rng.permutation(
        len(candidats)
    )

    selection = []

    for indice in ordre:

        candidat = candidats[
            indice
        ]

        if chevauche(
            candidat,
            selection,
            longueur,
        ):
            continue

        selection.append(
            candidat
        )

        if len(selection) >= nombre:
            break

    return selection


# =============================================================================
# METHODES D'IMPUTATION
# =============================================================================

def prediction_lineaire(
    matrice,
    station,
    debut_position,
    longueur,
):
    """M1 : interpolation linéaire entre les deux extrémités observées."""

    serie = matrice[station]

    position_avant = (
        debut_position - 1
    )

    position_apres = (
        debut_position
        + longueur
    )

    valeur_avant = float(
        serie.iloc[
            position_avant
        ]
    )

    valeur_apres = float(
        serie.iloc[
            position_apres
        ]
    )

    predictions = []

    # longueur points cachés donnent longueur + 1 intervalles entre
    # l'observation avant et l'observation après.
    for k in range(
        1,
        longueur + 1,
    ):

        poids = (
            k
            / (longueur + 1)
        )

        prediction = (
            (1 - poids)
            * valeur_avant
            + poids
            * valeur_apres
        )

        predictions.append(
            prediction
        )

    return np.array(
        predictions,
        dtype=float,
    )


def prediction_journaliere(
    matrice,
    station,
    debut_position,
    longueur,
):
    """M2 : moyenne de la veille et du lendemain à la même heure."""

    serie = matrice[station]

    decalage = int(
        24 / PAS_HEURES
    )

    predictions = []

    for k in range(
        longueur
    ):

        position = (
            debut_position + k
        )

        valeur_avant = float(
            serie.iloc[
                position - decalage
            ]
        )

        valeur_apres = float(
            serie.iloc[
                position + decalage
            ]
        )

        prediction = (
            valeur_avant
            + valeur_apres
        ) / 2

        predictions.append(
            prediction
        )

    return np.array(
        predictions,
        dtype=float,
    )


def prediction_hybride(
    predictions_lineaires,
    predictions_journalieres,
):
    """M3 : moyenne des prédictions M1 et M2."""

    return (
        predictions_lineaires
        + predictions_journalieres
    ) / 2


# =============================================================================
# EVALUATION D'UNE SEQUENCE
# =============================================================================

def evaluer_sequence(
    matrice,
    station,
    debut_position,
    longueur,
    id_sequence,
):
    """Évalue les trois méthodes sur une séquence artificielle."""

    verite = (
        matrice[station]
        .iloc[
            debut_position:
            debut_position + longueur
        ]
        .to_numpy(
            dtype=float
        )
    )

    dates = (
        matrice.index[
            debut_position:
            debut_position + longueur
        ]
    )

    pred_m1 = prediction_lineaire(
        matrice=matrice,
        station=station,
        debut_position=debut_position,
        longueur=longueur,
    )

    pred_m2 = prediction_journaliere(
        matrice=matrice,
        station=station,
        debut_position=debut_position,
        longueur=longueur,
    )

    pred_m3 = prediction_hybride(
        predictions_lineaires=pred_m1,
        predictions_journalieres=pred_m2,
    )

    serie = matrice[station].to_numpy(dtype=float)
    fin_position = debut_position + longueur - 1

    # La valeur à prédire est cachée : les méthodes causales n'utilisent que le
    # passé (positions < debut_position), elles ne la voient donc jamais.
    pred_causales = {
        methode: np.asarray(
            FONCTIONS_METHODES[methode](serie, debut_position, fin_position),
            dtype=float,
        )
        for methode in METHODES_CAUSALES
    }

    lignes = []

    for k in range(
        longueur
    ):

        lignes.append(
            {
                "id_sequence":
                    id_sequence,

                "station":
                    station,

                "timestamp":
                    dates[k],

                "longueur_sequence":
                    longueur,

                "duree_heures":
                    longueur
                    * PAS_HEURES,

                "position_dans_sequence":
                    k + 1,

                "temperature_reelle":
                    verite[k],

                "prediction_lineaire":
                    pred_m1[k],

                "prediction_journaliere":
                    pred_m2[k],

                "prediction_hybride":
                    pred_m3[k],

                **{
                    METHODES[methode]: pred_causales[methode][k]
                    for methode in METHODES_CAUSALES
                },
            }
        )

    return lignes


# =============================================================================
# CONSTRUCTION DU BENCHMARK
# =============================================================================

def construire_benchmark(
    matrice,
):
    """Construit et exécute le benchmark pour toutes les longueurs."""

    rng = np.random.default_rng(
        RANDOM_STATE
    )

    toutes_predictions = []

    id_sequence = 0

    for longueur in LONGUEURS:

        print()
        print("=" * 90)
        print(
            f"PREPARATION - {longueur} POINT(S) "
            f"= {longueur * PAS_HEURES} H"
        )
        print("=" * 90)

        print(
            "Recherche des séquences candidates..."
        )

        candidats = construire_candidats(
            matrice=matrice,
            longueur=longueur,
        )

        print(
            "Candidats disponibles :",
            len(candidats),
        )

        nombre_demande = (
            NB_SEQUENCES_PAR_LONGUEUR[
                longueur
            ]
        )

        selection = (
            echantillonner_sequences(
                candidats=candidats,
                longueur=longueur,
                nombre=nombre_demande,
                rng=rng,
            )
        )

        print(
            "Séquences sélectionnées :",
            len(selection),
        )

        if not selection:
            raise RuntimeError(
                "Aucune séquence disponible "
                f"pour longueur={longueur}."
            )

        print(
            "Nombre de températures évaluées :",
            len(selection)
            * longueur,
        )

        for (
            station,
            debut_position,
        ) in selection:

            id_sequence += 1

            lignes = evaluer_sequence(
                matrice=matrice,
                station=station,
                debut_position=debut_position,
                longueur=longueur,
                id_sequence=id_sequence,
            )

            toutes_predictions.extend(
                lignes
            )

    return pd.DataFrame(
        toutes_predictions
    )


# =============================================================================
# METRIQUES
# =============================================================================

def calculer_metriques(
    reel,
    prediction,
):
    """Calcule MAE, RMSE et biais."""

    reel = np.asarray(
        reel,
        dtype=float,
    )

    prediction = np.asarray(
        prediction,
        dtype=float,
    )

    erreurs = (
        prediction - reel
    )

    mae = np.mean(
        np.abs(erreurs)
    )

    rmse = np.sqrt(
        np.mean(
            erreurs ** 2
        )
    )

    biais = np.mean(
        erreurs
    )

    return {
        "MAE": mae,
        "RMSE": rmse,
        "biais": biais,
    }


def tableau_resultats(
    predictions,
):
    """Construit le tableau des performances par longueur et méthode."""

    correspondance = METHODES

    lignes = []

    for longueur in LONGUEURS:

        sous_table = predictions[
            predictions[
                "longueur_sequence"
            ]
            == longueur
        ]

        for (
            methode,
            colonne,
        ) in correspondance.items():

            metriques = calculer_metriques(
                reel=sous_table[
                    "temperature_reelle"
                ],
                prediction=sous_table[
                    colonne
                ],
            )

            lignes.append(
                {
                    "longueur_points":
                        longueur,

                    "duree_heures":
                        longueur
                        * PAS_HEURES,

                    "methode":
                        methode,

                    "n_temperatures":
                        len(
                            sous_table
                        ),

                    "MAE":
                        metriques["MAE"],

                    "RMSE":
                        metriques["RMSE"],

                    "biais":
                        metriques["biais"],
                }
            )

    return pd.DataFrame(
        lignes
    )


def tableau_global(
    predictions,
):
    """Calcule les performances globales des méthodes."""

    correspondance = METHODES

    lignes = []

    for (
        methode,
        colonne,
    ) in correspondance.items():

        metriques = calculer_metriques(
            reel=predictions[
                "temperature_reelle"
            ],
            prediction=predictions[
                colonne
            ],
        )

        lignes.append(
            {
                "methode":
                    methode,

                "n_temperatures":
                    len(predictions),

                "MAE":
                    metriques["MAE"],

                "RMSE":
                    metriques["RMSE"],

                "biais":
                    metriques["biais"],
            }
        )

    return pd.DataFrame(
        lignes
    )


# =============================================================================
# GAGNANTS
# =============================================================================

def afficher_meilleure_methode_par_longueur(
    resultats,
):
    """Affiche la meilleure méthode selon MAE et RMSE."""

    print()
    print("=" * 90)
    print(
        "MEILLEURE METHODE PAR LONGUEUR"
    )
    print("=" * 90)

    for longueur in LONGUEURS:

        sous_table = (
            resultats[
                (resultats["longueur_points"] == longueur)
                & resultats["methode"].isin(METHODES_CAUSALES)
            ]
        )

        meilleure_mae = (
            sous_table
            .sort_values("MAE")
            .iloc[0]
        )

        meilleure_rmse = (
            sous_table
            .sort_values("RMSE")
            .iloc[0]
        )

        print()
        print(
            f"{longueur} point(s) "
            f"= {longueur * PAS_HEURES} h"
        )

        print(
            "  Meilleure MAE  :",
            meilleure_mae[
                "methode"
            ],
            f"({meilleure_mae['MAE']:.4f} °C)",
        )

        print(
            "  Meilleur RMSE :",
            meilleure_rmse[
                "methode"
            ],
            f"({meilleure_rmse['RMSE']:.4f} °C)",
        )


# =============================================================================
# CONTROLES
# =============================================================================

def verifier_benchmark(
    predictions,
):
    """Vérifie la cohérence du benchmark."""

    print()
    print("=" * 90)
    print(
        "CONTROLES DU BENCHMARK"
    )
    print("=" * 90)

    colonnes_predictions = list(
        METHODES.values()
    )

    assert (
        predictions[
            "temperature_reelle"
        ]
        .notna()
        .all()
    )

    for colonne in (
        colonnes_predictions
    ):
        assert (
            predictions[
                colonne
            ]
            .notna()
            .all()
        )

    # M3 doit être exactement la moyenne de M1 et M2.
    attendu = (
        predictions[
            "prediction_lineaire"
        ]
        + predictions[
            "prediction_journaliere"
        ]
    ) / 2

    assert np.allclose(
        predictions[
            "prediction_hybride"
        ],
        attendu,
    )

    assert set(
        predictions[
            "longueur_sequence"
        ].unique()
    ) == set(
        LONGUEURS
    )

    print(
        "Températures évaluées :",
        len(predictions),
    )

    print(
        "Séquences évaluées :",
        predictions[
            "id_sequence"
        ].nunique(),
    )

    print(
        "Valeurs manquantes dans "
        "les prédictions : 0"
    )

    print(
        "Contrôles : OK"
    )


# =============================================================================
# AFFICHAGE DES RESULTATS
# =============================================================================

def afficher_resultats(
    resultats,
    global_,
):
    """Affiche les tableaux de résultats."""

    print()
    print("=" * 90)
    print(
        "RESULTATS PAR LONGUEUR DE TROU"
    )
    print("=" * 90)

    affichage = (
        resultats.copy()
    )

    affichage[
        "MAE"
    ] = affichage[
        "MAE"
    ].map(
        lambda x: f"{x:.4f}"
    )

    affichage[
        "RMSE"
    ] = affichage[
        "RMSE"
    ].map(
        lambda x: f"{x:.4f}"
    )

    affichage[
        "biais"
    ] = affichage[
        "biais"
    ].map(
        lambda x: f"{x:+.4f}"
    )

    print(
        affichage.to_string(
            index=False
        )
    )

    print()
    print("=" * 90)
    print(
        "RESULTATS GLOBAUX"
    )
    print("=" * 90)

    affichage_global = (
        global_.copy()
    )

    affichage_global[
        "MAE"
    ] = affichage_global[
        "MAE"
    ].map(
        lambda x: f"{x:.4f}"
    )

    affichage_global[
        "RMSE"
    ] = affichage_global[
        "RMSE"
    ].map(
        lambda x: f"{x:.4f}"
    )

    affichage_global[
        "biais"
    ] = affichage_global[
        "biais"
    ].map(
        lambda x: f"{x:+.4f}"
    )

    print(
        affichage_global.to_string(
            index=False
        )
    )


# =============================================================================
# EXEMPLES
# =============================================================================

def afficher_exemples(
    predictions,
):
    """Affiche quelques prédictions pour chaque longueur."""

    print()
    print("=" * 90)
    print(
        "EXEMPLES DE PREDICTIONS"
    )
    print("=" * 90)

    colonnes = [
        "station",
        "timestamp",
        "longueur_sequence",
        "position_dans_sequence",
        "temperature_reelle",
        *METHODES.values(),
    ]

    for longueur in LONGUEURS:

        print()
        print(
            f"--- {longueur} point(s) "
            f"= {longueur * PAS_HEURES} h ---"
        )

        exemples = (
            predictions[
                predictions[
                    "longueur_sequence"
                ]
                == longueur
            ]
            .head(8)
        )

        print(
            exemples[
                colonnes
            ]
            .to_string(
                index=False
            )
        )


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sauvegarder(
    predictions,
    resultats,
):
    """Sauvegarde les prédictions et les résultats."""

    DOSSIER_METEO.mkdir(
        parents=True,
        exist_ok=True,
    )

    predictions.to_csv(
        FICHIER_PREDICTIONS,
        index=False,
    )

    resultats.to_csv(
        FICHIER_RESULTATS,
        index=False,
    )


# =============================================================================
# EXECUTION
# =============================================================================

def main():

    print("=" * 90)
    print(
        "BENCHMARK D'IMPUTATION "
        "TEMPORELLE SYNOP"
    )
    print("=" * 90)

    # =========================================================================
    # 1. LECTURE
    # =========================================================================

    print()
    print(
        "Lecture de la matrice après "
        "imputation spatiale..."
    )

    matrice = lire_matrice()

    sequences_reelles = (
        lire_sequences_reelles()
    )

    print()
    print(
        "Dimensions :",
        matrice.shape,
    )

    print(
        "Valeurs encore manquantes :",
        int(
            matrice
            .isna()
            .sum()
            .sum()
        ),
    )

    # =========================================================================
    # 2. STRUCTURE DES TROUS REELS
    # =========================================================================

    afficher_structure_reelle(
        sequences_reelles
    )

    # =========================================================================
    # 3. BENCHMARK
    # =========================================================================

    predictions = (
        construire_benchmark(
            matrice
        )
    )

    # =========================================================================
    # 4. CONTROLES
    # =========================================================================

    verifier_benchmark(
        predictions
    )

    # =========================================================================
    # 5. METRIQUES
    # =========================================================================

    resultats = (
        tableau_resultats(
            predictions
        )
    )

    global_ = (
        tableau_global(
            predictions
        )
    )

    # =========================================================================
    # 6. RESULTATS
    # =========================================================================

    afficher_resultats(
        resultats,
        global_,
    )

    afficher_meilleure_methode_par_longueur(
        resultats
    )

    afficher_exemples(
        predictions
    )

    # =========================================================================
    # 7. SAUVEGARDE
    # =========================================================================

    sauvegarder(
        predictions,
        resultats,
    )

    print()
    print("=" * 90)
    print(
        "FICHIERS CREES"
    )
    print("=" * 90)

    print(
        "Prédictions :",
        FICHIER_PREDICTIONS,
    )

    print(
        "Résultats :",
        FICHIER_RESULTATS,
    )

    print()
    print(
        "Benchmark temporel terminé."
    )

    print(
        "Aucune valeur réellement "
        "manquante n'a été modifiée."
    )


# =============================================================================
# LANCEMENT
# =============================================================================

if __name__ == "__main__":
    main()