"""
Modèles linéaires M2 avec information météorologique.

M2 prolonge M1 en ajoutant des variables de température causales.

Principes
---------
- Un modèle indépendant par heure cible H.
- Même structure de retards que M1.
- Même calendrier que M1.
- Même encodage catégoriel que M1.
- Même validation chronologique 2023 en quatre blocs expanding.
- Une seule représentation nationale de température est utilisée à la fois.
- Les données 2024-2025 ne sont jamais utilisées pour sélectionner
  la représentation ou la spécification météorologique.
- Les variables de météo parfaite sont interdites.
- L'évaluation finale 2024-2025 est mensuelle expanding.
- Pendant l'évaluation finale, seules les cibles strictement
  antérieures au mois courant peuvent entrer dans l'apprentissage.

Candidats de température
------------------------
- temp_8_villes
- temp_38_simple
- temp_38_ponderee

Variantes d'ablation
--------------------
M2-A :
    température à l'origine.

M2-B :
    température à l'origine + température de la veille.

M2-C :
    origine + veille + température lissée.

M2-D :
    origine + température lissée
    + degrés de chauffage à l'origine et lissés.

M2-E :
    origine + température lissée
    + degrés de chauffage à l'origine et lissés
    + degrés de climatisation à l'origine et lissés.

M2-F :
    les sept variables météorologiques.
    Cette variante reproduit le M2 initial.

Sélection
---------
Le critère principal est la MAE globale sur la validation 2023.

La RMSE, les performances trimestrielles et les performances
horaires sont des diagnostics secondaires.

La configuration finale doit être gelée à partir de la validation
2023 avant toute évaluation sur 2024-2025.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src import modeles_lineaires


# ============================================================
# Constantes générales
# ============================================================

COLONNE_CIBLE = modeles_lineaires.COLONNE_CIBLE
COLONNE_HEURE = modeles_lineaires.COLONNE_HEURE
COLONNE_PERIODE = modeles_lineaires.COLONNE_PERIODE
COLONNE_COVID = modeles_lineaires.COLONNE_COVID
COLONNE_JOUR = modeles_lineaires.COLONNE_JOUR


CANDIDATS_TEMPERATURE = [
    "temp_8_villes",
    "temp_38_simple",
    "temp_38_ponderee",
]


# ============================================================
# Suffixes météo
# ============================================================

SUFFIXE_ORIGINE = "origine"
SUFFIXE_VEILLE = "veille"
SUFFIXE_LISSEE = "lissee"

SUFFIXE_CHAUFFAGE_ORIGINE = (
    "degres_chauffage_origine"
)

SUFFIXE_CHAUFFAGE_LISSES = (
    "degres_chauffage_lisses"
)

SUFFIXE_CLIMATISATION_ORIGINE = (
    "degres_climatisation_origine"
)

SUFFIXE_CLIMATISATION_LISSES = (
    "degres_climatisation_lisses"
)


SUFFIXES_METEO_M2 = [
    SUFFIXE_ORIGINE,
    SUFFIXE_VEILLE,
    SUFFIXE_LISSEE,
    SUFFIXE_CHAUFFAGE_ORIGINE,
    SUFFIXE_CHAUFFAGE_LISSES,
    SUFFIXE_CLIMATISATION_ORIGINE,
    SUFFIXE_CLIMATISATION_LISSES,
]


# ============================================================
# Variantes d'ablation
# ============================================================

VARIANTES_METEO_M2 = {
    "M2-A": [
        SUFFIXE_ORIGINE,
    ],

    "M2-B": [
        SUFFIXE_ORIGINE,
        SUFFIXE_VEILLE,
    ],

    "M2-C": [
        SUFFIXE_ORIGINE,
        SUFFIXE_VEILLE,
        SUFFIXE_LISSEE,
    ],

    "M2-D": [
        SUFFIXE_ORIGINE,
        SUFFIXE_LISSEE,
        SUFFIXE_CHAUFFAGE_ORIGINE,
        SUFFIXE_CHAUFFAGE_LISSES,
    ],

    "M2-E": [
        SUFFIXE_ORIGINE,
        SUFFIXE_LISSEE,
        SUFFIXE_CHAUFFAGE_ORIGINE,
        SUFFIXE_CHAUFFAGE_LISSES,
        SUFFIXE_CLIMATISATION_ORIGINE,
        SUFFIXE_CLIMATISATION_LISSES,
    ],

    "M2-F": [
        SUFFIXE_ORIGINE,
        SUFFIXE_VEILLE,
        SUFFIXE_LISSEE,
        SUFFIXE_CHAUFFAGE_ORIGINE,
        SUFFIXE_CHAUFFAGE_LISSES,
        SUFFIXE_CLIMATISATION_ORIGINE,
        SUFFIXE_CLIMATISATION_LISSES,
    ],
}


VARIANTE_METEO_DEFAUT = "M2-F"


# ============================================================
# Structures de résultats
# ============================================================

@dataclass
class ResultatValidationM2:
    candidat_temperature: str
    predictions: pd.DataFrame
    metriques: dict[str, float]
    variante_meteo: str = VARIANTE_METEO_DEFAUT


@dataclass
class ResultatComparaisonM2:
    resultats: dict[str, ResultatValidationM2]
    tableau: pd.DataFrame


@dataclass
class ResultatAblationM2:
    resultats: dict[
        tuple[str, str],
        ResultatValidationM2,
    ]
    tableau: pd.DataFrame


@dataclass
class ResultatTestFinalM2:
    candidat_temperature: str
    variante_meteo: str
    predictions: pd.DataFrame
    metriques: dict[str, float]


# ============================================================
# Vérifications
# ============================================================

def verifier_candidat_temperature(
    candidat: str,
) -> None:
    """
    Vérifie que le candidat de température est autorisé.
    """

    if candidat not in CANDIDATS_TEMPERATURE:
        raise ValueError(
            "Candidat température inconnu : "
            f"{candidat}. "
            "Candidats autorisés : "
            + ", ".join(CANDIDATS_TEMPERATURE)
        )


def verifier_variante_meteo(
    variante: str,
) -> None:
    """
    Vérifie que la variante météo est autorisée.
    """

    if variante not in VARIANTES_METEO_M2:
        raise ValueError(
            "Variante météo inconnue : "
            f"{variante}. "
            "Variantes autorisées : "
            + ", ".join(VARIANTES_METEO_M2)
        )


def verifier_absence_meteo_parfaite(
    colonnes: list[str],
) -> None:
    """
    Interdit toute variable utilisant la météo parfaite.
    """

    interdites = [
        colonne
        for colonne in colonnes
        if "meteo_parfaite" in colonne
    ]

    if interdites:
        raise ValueError(
            "Les variables de météo parfaite "
            "sont interdites dans M2 : "
            + ", ".join(interdites)
        )


# ============================================================
# Variables météorologiques
# ============================================================

def suffixes_meteo_m2(
    variante: str = VARIANTE_METEO_DEFAUT,
) -> list[str]:
    """
    Retourne les suffixes météo d'une variante.
    """

    verifier_variante_meteo(variante)

    return list(
        VARIANTES_METEO_M2[variante]
    )


def variables_meteo_m2(
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> list[str]:
    """
    Retourne les variables météo d'un candidat
    pour une variante donnée.
    """

    verifier_candidat_temperature(candidat)
    verifier_variante_meteo(variante)

    variables = [
        f"{candidat}_{suffixe}"
        for suffixe in suffixes_meteo_m2(
            variante
        )
    ]

    verifier_absence_meteo_parfaite(
        variables
    )

    return variables


# ============================================================
# Variables M2
# ============================================================

def variables_numeriques_m2(
    heure: int,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> list[str]:
    """
    Variables numériques de M2 :
    variables numériques M1 + variables météo.
    """

    modeles_lineaires.verifier_heure(
        heure
    )

    return (
        modeles_lineaires
        .variables_numeriques_m1(
            heure
        )
        + variables_meteo_m2(
            candidat,
            variante,
        )
    )


def variables_m2(
    heure: int,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> list[str]:
    """
    Ensemble complet des variables explicatives M2.
    """

    variables = (
        variables_numeriques_m2(
            heure,
            candidat,
            variante,
        )
        + list(
            modeles_lineaires
            .VARIABLES_CATEGORIELLES_M1
        )
    )

    verifier_absence_meteo_parfaite(
        variables
    )

    return variables


# ============================================================
# Construction du modèle
# ============================================================

def construire_modele_m2(
    heure: int,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> Pipeline:
    """
    Construit le pipeline M2 pour une heure cible.
    """

    modeles_lineaires.verifier_heure(
        heure
    )

    verifier_candidat_temperature(
        candidat
    )

    verifier_variante_meteo(
        variante
    )

    numeriques = (
        variables_numeriques_m2(
            heure,
            candidat,
            variante,
        )
    )

    preparation = ColumnTransformer(
        transformers=[
            (
                "categoriel",
                OneHotEncoder(
                    categories=[
                        list(range(7)),
                        list(range(1, 13)),
                    ],
                    drop="first",
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                modeles_lineaires
                .VARIABLES_CATEGORIELLES_M1,
            ),
            (
                "numerique",
                "passthrough",
                numeriques,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    return Pipeline(
        steps=[
            (
                "preparation",
                preparation,
            ),
            (
                "regression",
                LinearRegression(),
            ),
        ]
    )


# ============================================================
# Ajustement
# ============================================================

def ajuster_modeles_m2(
    apprentissage: pd.DataFrame,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> dict[int, Pipeline]:
    """
    Ajuste un modèle M2 indépendant pour chacune des 24 heures.
    """

    verifier_candidat_temperature(
        candidat
    )

    verifier_variante_meteo(
        variante
    )

    modeles_lineaires.verifier_colonnes(
        apprentissage,
        [
            COLONNE_HEURE,
            COLONNE_CIBLE,
        ],
    )

    modeles: dict[int, Pipeline] = {}

    for heure in range(24):

        variables = variables_m2(
            heure,
            candidat,
            variante,
        )

        modeles_lineaires.verifier_colonnes(
            apprentissage,
            variables,
        )

        donnees_h = apprentissage.loc[
            apprentissage[
                COLONNE_HEURE
            ] == heure
        ]

        if donnees_h.empty:
            raise ValueError(
                "Aucune observation "
                "d'apprentissage pour "
                f"l'heure {heure}."
            )

        X = donnees_h[
            variables
        ]

        y = donnees_h[
            COLONNE_CIBLE
        ]

        if X.isna().any().any():
            raise ValueError(
                "NaN dans les variables M2 "
                f"pour l'heure {heure}, "
                f"{candidat}, {variante}."
            )

        if y.isna().any():
            raise ValueError(
                "NaN dans la cible M2 "
                f"pour l'heure {heure}."
            )

        modele = construire_modele_m2(
            heure,
            candidat,
            variante,
        )

        modele.fit(
            X,
            y,
        )

        modeles[
            heure
        ] = modele

    return modeles


# ============================================================
# Prédiction
# ============================================================

def predire_m2(
    modeles: dict[int, Pipeline],
    donnees: pd.DataFrame,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> pd.DataFrame:
    """
    Produit les prédictions M2.
    """

    verifier_candidat_temperature(
        candidat
    )

    verifier_variante_meteo(
        variante
    )

    modeles_lineaires.verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
        ],
    )

    morceaux = []

    for heure in range(24):

        if heure not in modeles:
            raise ValueError(
                "Modèle M2 absent pour "
                f"l'heure {heure}."
            )

        variables = variables_m2(
            heure,
            candidat,
            variante,
        )

        modeles_lineaires.verifier_colonnes(
            donnees,
            variables,
        )

        donnees_h = donnees.loc[
            donnees[
                COLONNE_HEURE
            ] == heure
        ].copy()

        if donnees_h.empty:
            continue

        X = donnees_h[
            variables
        ]

        if X.isna().any().any():
            raise ValueError(
                "NaN dans les variables "
                "de prédiction pour "
                f"{candidat}, {variante}, "
                f"heure {heure}."
            )

        donnees_h[
            "prediction_MW"
        ] = modeles[
            heure
        ].predict(
            X
        )

        colonnes_sortie = [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            "prediction_MW",
        ]

        if (
            "bloc_validation"
            in donnees_h.columns
        ):
            colonnes_sortie.append(
                "bloc_validation"
            )

        if (
            "bloc_test"
            in donnees_h.columns
        ):
            colonnes_sortie.append(
                "bloc_test"
            )

        morceaux.append(
            donnees_h[
                colonnes_sortie
            ]
        )

    if not morceaux:
        raise ValueError(
            "Aucune prédiction M2 produite."
        )

    predictions = (
        pd.concat(
            morceaux,
            ignore_index=True,
        )
        .sort_values(
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return predictions


# ============================================================
# Validation expanding 2023
# ============================================================

def valider_m2_expanding(
    donnees: pd.DataFrame,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> ResultatValidationM2:
    """
    Validation chronologique M2 sur 2023.

    Quatre blocs trimestriels sont utilisés avec
    ré-estimation expanding avant chaque bloc.

    Cette fonction reste strictement réservée à la
    sélection/validation 2023.
    """

    verifier_candidat_temperature(
        candidat
    )

    verifier_variante_meteo(
        variante
    )

    modeles_lineaires.verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            COLONNE_COVID,
            COLONNE_PERIODE,
        ],
    )

    jours = pd.to_datetime(
        donnees[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in (
        modeles_lineaires
        .BLOCS_VALIDATION_2023
    ):

        apprentissage = (
            modeles_lineaires
            .apprentissage_avant(
                donnees,
                debut,
                periodes_autorisees=(
                    modeles_lineaires
                    .PERIODES_AUTORISEES_VALIDATION_EXPANDING
                ),
            )
        )

        masque_validation = (
            (
                donnees[
                    COLONNE_PERIODE
                ]
                == "validation"
            )
            & (
                jours >= debut
            )
            & (
                jours < fin
            )
        )

        validation_bloc = (
            donnees.loc[
                masque_validation
            ].copy()
        )

        if validation_bloc.empty:
            raise ValueError(
                f"Bloc {nom_bloc} vide."
            )

        validation_bloc[
            "bloc_validation"
        ] = nom_bloc

        modeles = ajuster_modeles_m2(
            apprentissage,
            candidat,
            variante,
        )

        predictions = predire_m2(
            modeles,
            validation_bloc,
            candidat,
            variante,
        )

        morceaux.append(
            predictions
        )

    predictions = (
        pd.concat(
            morceaux,
            ignore_index=True,
        )
        .sort_values(
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
            ]
        )
        .reset_index(
            drop=True
        )
    )

    metriques = (
        modeles_lineaires
        .calculer_metriques(
            predictions
        )
    )

    metriques.update(
        modeles_lineaires
        .calculer_metriques_journalieres(
            predictions
        )
    )

    return ResultatValidationM2(
        candidat_temperature=candidat,
        predictions=predictions,
        metriques=metriques,
        variante_meteo=variante,
    )


# ============================================================
# Évaluation finale mensuelle 2024-2025
# ============================================================

def evaluer_m2_test_final(
    donnees: pd.DataFrame,
    candidat: str,
    variante: str = VARIANTE_METEO_DEFAUT,
) -> ResultatTestFinalM2:
    """
    Évalue M2 sur le test final 2024-2025.

    IMPORTANT
    ---------
    Cette fonction ne doit être exécutée qu'après gel définitif
    de la configuration sur la validation 2023.

    Le modèle est ré-estimé au début de chaque mois.

    Pour un mois donné, l'apprentissage peut contenir :
    - apprentissage 2016-2022 ;
    - validation 2023 ;
    - mois de test strictement antérieurs.

    Le mois courant et tous les mois futurs sont exclus grâce à
    la condition temporelle stricte appliquée par
    modeles_lineaires.apprentissage_avant().
    """

    verifier_candidat_temperature(
        candidat
    )

    verifier_variante_meteo(
        variante
    )

    modeles_lineaires.verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            COLONNE_COVID,
            COLONNE_PERIODE,
        ],
    )

    jours = pd.to_datetime(
        donnees[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in (
        modeles_lineaires
        .BLOCS_TEST_FINAL_2024_2025
    ):

        apprentissage = (
            modeles_lineaires
            .apprentissage_avant(
                donnees,
                debut,
                periodes_autorisees=(
                    modeles_lineaires
                    .PERIODES_AUTORISEES_TEST_FINAL
                ),
            )
        )

        masque_test = (
            (
                donnees[
                    COLONNE_PERIODE
                ]
                == "test"
            )
            & (
                jours >= debut
            )
            & (
                jours < fin
            )
        )

        test_bloc = (
            donnees.loc[
                masque_test
            ].copy()
        )

        if test_bloc.empty:
            raise ValueError(
                f"Bloc de test {nom_bloc} vide."
            )

        test_bloc[
            "bloc_test"
        ] = nom_bloc

        modeles = ajuster_modeles_m2(
            apprentissage,
            candidat,
            variante,
        )

        predictions = predire_m2(
            modeles,
            test_bloc,
            candidat,
            variante,
        )

        morceaux.append(
            predictions
        )

    if not morceaux:
        raise ValueError(
            "Aucune prédiction M2 de test final produite."
        )

    predictions = (
        pd.concat(
            morceaux,
            ignore_index=True,
        )
        .sort_values(
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
            ]
        )
        .reset_index(
            drop=True
        )
    )

    metriques = (
        modeles_lineaires
        .calculer_metriques(
            predictions
        )
    )

    metriques.update(
        modeles_lineaires
        .calculer_metriques_journalieres(
            predictions
        )
    )

    return ResultatTestFinalM2(
        candidat_temperature=candidat,
        variante_meteo=variante,
        predictions=predictions,
        metriques=metriques,
    )


# ============================================================
# Métriques par trimestre
# ============================================================

def metriques_par_bloc(
    resultat: ResultatValidationM2,
) -> pd.DataFrame:
    """
    Calcule MAE et RMSE pour chaque bloc trimestriel.
    """

    predictions = (
        resultat.predictions
    )

    modeles_lineaires.verifier_colonnes(
        predictions,
        [
            "bloc_validation",
            COLONNE_CIBLE,
            "prediction_MW",
        ],
    )

    lignes = []

    for bloc in [
        "T1",
        "T2",
        "T3",
        "T4",
    ]:

        donnees_bloc = predictions.loc[
            predictions[
                "bloc_validation"
            ] == bloc
        ]

        if donnees_bloc.empty:
            continue

        y = donnees_bloc[
            COLONNE_CIBLE
        ].to_numpy()

        y_pred = donnees_bloc[
            "prediction_MW"
        ].to_numpy()

        lignes.append(
            {
                "bloc": bloc,
                "n": len(
                    donnees_bloc
                ),
                "MAE_MW": float(
                    mean_absolute_error(
                        y,
                        y_pred,
                    )
                ),
                "RMSE_MW": float(
                    np.sqrt(
                        mean_squared_error(
                            y,
                            y_pred,
                        )
                    )
                ),
            }
        )

    return pd.DataFrame(
        lignes
    )


# ============================================================
# Comparaison historique M2-F
# ============================================================

def comparer_candidats_m2(
    donnees: pd.DataFrame,
) -> ResultatComparaisonM2:
    """
    Compare les trois candidats de température avec M2-F.

    Cette fonction conserve le comportement du M2 initial
    afin de pouvoir reproduire les résultats déjà obtenus.
    """

    resultats = {}
    lignes = []

    for candidat in (
        CANDIDATS_TEMPERATURE
    ):

        resultat = (
            valider_m2_expanding(
                donnees,
                candidat,
                VARIANTE_METEO_DEFAUT,
            )
        )

        resultats[
            candidat
        ] = resultat

        lignes.append(
            {
                "candidat_temperature":
                    candidat,

                "MAE_MW":
                    resultat.metriques[
                        "MAE_MW"
                    ],

                "RMSE_MW":
                    resultat.metriques[
                        "RMSE_MW"
                    ],

                "MAE_total_journalier_MWh":
                    resultat.metriques[
                        "MAE_total_journalier_MWh"
                    ],

                "MAE_pointe_MW":
                    resultat.metriques[
                        "MAE_pointe_MW"
                    ],

                "MAE_heure_pointe_h":
                    resultat.metriques[
                        "MAE_heure_pointe_h"
                    ],

                "nb_jours_complets":
                    resultat.metriques[
                        "nb_jours_complets"
                    ],
            }
        )

    tableau = (
        pd.DataFrame(
            lignes
        )
        .sort_values(
            [
                "MAE_MW",
                "RMSE_MW",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return ResultatComparaisonM2(
        resultats=resultats,
        tableau=tableau,
    )


# ============================================================
# Ablation complète
# ============================================================

def comparer_ablations_m2(
    donnees: pd.DataFrame,
) -> ResultatAblationM2:
    """
    Compare les 18 configurations M2 :

        3 candidats de température
        x
        6 variantes météorologiques.

    Le classement principal est effectué selon :
        1. MAE globale 2023
        2. RMSE globale 2023
        3. nombre de variables météo

    Les données 2024-2025 ne sont pas utilisées.
    """

    resultats = {}
    lignes = []

    for candidat in (
        CANDIDATS_TEMPERATURE
    ):

        for variante in (
            VARIANTES_METEO_M2
        ):

            resultat = (
                valider_m2_expanding(
                    donnees,
                    candidat,
                    variante,
                )
            )

            cle = (
                candidat,
                variante,
            )

            resultats[
                cle
            ] = resultat

            lignes.append(
                {
                    "candidat_temperature":
                        candidat,

                    "variante_meteo":
                        variante,

                    "nb_variables_meteo":
                        len(
                            variables_meteo_m2(
                                candidat,
                                variante,
                            )
                        ),

                    "MAE_MW":
                        resultat.metriques[
                            "MAE_MW"
                        ],

                    "RMSE_MW":
                        resultat.metriques[
                            "RMSE_MW"
                        ],

                    "MAE_total_journalier_MWh":
                        resultat.metriques[
                            "MAE_total_journalier_MWh"
                        ],

                    "MAE_pointe_MW":
                        resultat.metriques[
                            "MAE_pointe_MW"
                        ],

                    "MAE_heure_pointe_h":
                        resultat.metriques[
                            "MAE_heure_pointe_h"
                        ],

                    "nb_jours_complets":
                        resultat.metriques[
                            "nb_jours_complets"
                        ],
                }
            )

    tableau = (
        pd.DataFrame(
            lignes
        )
        .sort_values(
            [
                "MAE_MW",
                "RMSE_MW",
                "nb_variables_meteo",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return ResultatAblationM2(
        resultats=resultats,
        tableau=tableau,
    )