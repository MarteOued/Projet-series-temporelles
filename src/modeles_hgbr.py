"""
Modèle M3 : Histogram Gradient Boosting Regressor.

M3 reprend exactement l'information disponible dans la configuration
M2 sélectionnée sur la validation 2023 :

- calendrier CAL-D ;
- retards de consommation LAG-B ;
- candidat météo temp_38_ponderee ;
- variante météo M2-F.

La différence entre M2 et M3 porte uniquement sur la famille de modèles :

    M2 : régression linéaire ;
    M3 : HistGradientBoostingRegressor.

Protocole
---------
- un modèle distinct pour chacune des 24 heures ;
- apprentissage strictement antérieur au bloc prédit ;
- validation expanding sur les quatre trimestres de 2023 ;
- test final 2024-2025 par blocs mensuels expanding ;
- exclusion des cibles COVID via apprentissage_avant() ;
- aucune variable de météo parfaite ;
- random_state fixé pour la reproductibilité.

Sélection M3
------------
La configuration M3 a été sélectionnée exclusivement sur la validation 2023.

Grille évaluée :
- M3-1 : learning_rate=0.05, max_iter=300, max_leaf_nodes=15, L2=1.0
- M3-2 : learning_rate=0.05, max_iter=300, max_leaf_nodes=31, L2=1.0
- M3-3 : learning_rate=0.05, max_iter=300, max_leaf_nodes=63, L2=1.0
- M3-4 : learning_rate=0.10, max_iter=200, max_leaf_nodes=31, L2=1.0

Critère principal :
    MAE globale sur 2023.

Configuration retenue :
    M3-1.

Résultats M3-1 sur 2023 :
    MAE  = 1579.716318 MW
    RMSE = 2251.868368 MW

Aucun résultat 2024-2025 n'a été utilisé pour sélectionner les
hyperparamètres de M3.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src import modeles_lineaires as m1
from src import modeles_meteo as m2


# ===========================================================================
# Configuration M3 gelée
# ===========================================================================

CANDIDAT_TEMPERATURE_M3 = "temp_38_ponderee"
VARIANTE_METEO_M3 = "M2-F"

RANDOM_STATE_M3 = 42

# Configuration M3-1 sélectionnée exclusivement sur la validation 2023.
LEARNING_RATE_M3 = 0.05
MAX_ITER_M3 = 300
MAX_LEAF_NODES_M3 = 15
L2_REGULARIZATION_M3 = 1.0


# ===========================================================================
# Structures de résultats
# ===========================================================================

@dataclass
class ResultatValidationM3:
    """
    Résultat complet d'une validation expanding de M3.
    """

    predictions: pd.DataFrame
    metriques: dict[str, float]
    metriques_par_bloc: pd.DataFrame
    parametres: dict[str, object]


@dataclass
class ResultatTestFinalM3:
    """
    Résultat de l'évaluation finale M3 sur 2024-2025.
    """

    configuration: str
    candidat_temperature: str
    variante_meteo: str
    predictions: pd.DataFrame
    metriques: dict[str, float]
    parametres: dict[str, object]


# ===========================================================================
# Vérifications
# ===========================================================================

def verifier_configuration_m3() -> None:
    """
    Vérifie que M3 utilise bien la configuration M2 gelée.
    """

    m2.verifier_candidat_temperature(
        CANDIDAT_TEMPERATURE_M3
    )

    m2.verifier_variante_meteo(
        VARIANTE_METEO_M3
    )

    if CANDIDAT_TEMPERATURE_M3 != "temp_38_ponderee":
        raise ValueError(
            "M3 doit utiliser le candidat météo gelé "
            "'temp_38_ponderee'."
        )

    if VARIANTE_METEO_M3 != "M2-F":
        raise ValueError(
            "M3 doit utiliser la variante météo gelée 'M2-F'."
        )


def verifier_hyperparametres_m3(
    learning_rate: float,
    max_iter: int,
    max_leaf_nodes: int,
    l2_regularization: float,
) -> None:
    """
    Vérifie les hyperparamètres principaux du HGBR.
    """

    if learning_rate <= 0:
        raise ValueError(
            "learning_rate doit être strictement positif."
        )

    if max_iter <= 0:
        raise ValueError(
            "max_iter doit être strictement positif."
        )

    if max_leaf_nodes < 2:
        raise ValueError(
            "max_leaf_nodes doit être supérieur ou égal à 2."
        )

    if l2_regularization < 0:
        raise ValueError(
            "l2_regularization doit être positif ou nul."
        )


def verifier_donnees_m3(
    donnees: pd.DataFrame,
) -> None:
    """
    Vérifie les propriétés minimales nécessaires à M3.
    """

    if not isinstance(
        donnees,
        pd.DataFrame,
    ):
        raise TypeError(
            "donnees doit être un pandas.DataFrame."
        )

    if donnees.empty:
        raise ValueError(
            "Le DataFrame fourni à M3 est vide."
        )

    colonnes_interdites = [
        colonne
        for colonne in donnees.columns
        if "meteo_parfaite" in colonne
    ]

    if colonnes_interdites:
        raise ValueError(
            "M3 ne doit jamais utiliser de météo parfaite : "
            + ", ".join(
                colonnes_interdites
            )
        )

    colonnes_requises = {
        "jour_cible",
        "heure_cible",
        "consommation_cible_MW",
        "periode",
    }

    manquantes = (
        colonnes_requises
        - set(donnees.columns)
    )

    if manquantes:
        raise ValueError(
            "Colonnes obligatoires manquantes pour M3 : "
            + ", ".join(
                sorted(manquantes)
            )
        )


# ===========================================================================
# Variables M3
# ===========================================================================

def variables_numeriques_m3(
    heure: int,
) -> list[str]:
    """
    Retourne les variables numériques M3 pour une heure donnée.

    Elles sont exactement celles de M2-F avec temp_38_ponderee.
    """

    verifier_configuration_m3()

    return m2.variables_numeriques_m2(
        heure=heure,
        candidat=CANDIDAT_TEMPERATURE_M3,
        variante=VARIANTE_METEO_M3,
    )


def variables_m3(
    heure: int,
) -> list[str]:
    """
    Retourne toutes les variables explicatives M3.

    L'ensemble est volontairement identique à celui de M2 gelé.
    """

    verifier_configuration_m3()

    return m2.variables_m2(
        heure=heure,
        candidat=CANDIDAT_TEMPERATURE_M3,
        variante=VARIANTE_METEO_M3,
    )


# ===========================================================================
# Construction du modèle
# ===========================================================================

def construire_modele_m3(
    heure: int,
    learning_rate: float = LEARNING_RATE_M3,
    max_iter: int = MAX_ITER_M3,
    max_leaf_nodes: int = MAX_LEAF_NODES_M3,
    l2_regularization: float = L2_REGULARIZATION_M3,
) -> Pipeline:
    """
    Construit le pipeline M3 pour une heure cible.
    """

    verifier_configuration_m3()

    verifier_hyperparametres_m3(
        learning_rate=learning_rate,
        max_iter=max_iter,
        max_leaf_nodes=max_leaf_nodes,
        l2_regularization=l2_regularization,
    )

    if heure not in range(24):
        raise ValueError(
            "heure doit être comprise entre 0 et 23."
        )

    variables_numeriques = variables_numeriques_m3(
        heure
    )

    variables_categorielles = list(
        m1.VARIABLES_CATEGORIELLES_M1
    )

    transformateur = ColumnTransformer(
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
                variables_categorielles,
            ),
            (
                "numerique",
                "passthrough",
                variables_numeriques,
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )

    regression = HistGradientBoostingRegressor(
        learning_rate=learning_rate,
        max_iter=max_iter,
        max_leaf_nodes=max_leaf_nodes,
        l2_regularization=l2_regularization,
        random_state=RANDOM_STATE_M3,
        early_stopping=False,
    )

    return Pipeline(
        steps=[
            (
                "preparation",
                transformateur,
            ),
            (
                "regression",
                regression,
            ),
        ]
    )


# ===========================================================================
# Apprentissage
# ===========================================================================

def ajuster_modeles_m3(
    apprentissage: pd.DataFrame,
    learning_rate: float = LEARNING_RATE_M3,
    max_iter: int = MAX_ITER_M3,
    max_leaf_nodes: int = MAX_LEAF_NODES_M3,
    l2_regularization: float = L2_REGULARIZATION_M3,
) -> dict[int, Pipeline]:
    """
    Ajuste les 24 modèles horaires M3.
    """

    verifier_donnees_m3(
        apprentissage
    )

    verifier_hyperparametres_m3(
        learning_rate=learning_rate,
        max_iter=max_iter,
        max_leaf_nodes=max_leaf_nodes,
        l2_regularization=l2_regularization,
    )

    modeles = {}

    for heure in range(24):

        donnees_heure = apprentissage.loc[
            apprentissage[
                "heure_cible"
            ] == heure
        ].copy()

        if donnees_heure.empty:
            raise ValueError(
                f"Aucune observation d'apprentissage "
                f"pour l'heure {heure}."
            )

        variables = variables_m3(
            heure
        )

        manquantes = [
            variable
            for variable in variables
            if variable not in donnees_heure.columns
        ]

        if manquantes:
            raise ValueError(
                f"Variables M3 manquantes pour H={heure} : "
                + ", ".join(
                    manquantes
                )
            )

        if donnees_heure[
            variables
        ].isna().any().any():
            raise ValueError(
                f"Valeurs manquantes dans les variables "
                f"M3 pour H={heure}."
            )

        if donnees_heure[
            "consommation_cible_MW"
        ].isna().any():
            raise ValueError(
                f"Valeurs cibles manquantes pour H={heure}."
            )

        modele = construire_modele_m3(
            heure=heure,
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes,
            l2_regularization=l2_regularization,
        )

        modele.fit(
            donnees_heure[
                variables
            ],
            donnees_heure[
                "consommation_cible_MW"
            ],
        )

        modeles[
            heure
        ] = modele

    if set(
        modeles.keys()
    ) != set(
        range(24)
    ):
        raise RuntimeError(
            "Les 24 modèles horaires M3 "
            "n'ont pas été ajustés."
        )

    return modeles


# ===========================================================================
# Prédiction
# ===========================================================================

def predire_m3(
    modeles: dict[int, Pipeline],
    donnees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produit les prédictions M3 pour les observations fournies.
    """

    verifier_donnees_m3(
        donnees
    )

    if set(
        modeles.keys()
    ) != set(
        range(24)
    ):
        raise ValueError(
            "Le dictionnaire de modèles doit contenir "
            "exactement les heures 0 à 23."
        )

    morceaux = []

    for heure in range(24):

        donnees_heure = donnees.loc[
            donnees[
                "heure_cible"
            ] == heure
        ].copy()

        if donnees_heure.empty:
            continue

        variables = variables_m3(
            heure
        )

        manquantes = [
            variable
            for variable in variables
            if variable not in donnees_heure.columns
        ]

        if manquantes:
            raise ValueError(
                f"Variables M3 manquantes pour H={heure} : "
                + ", ".join(
                    manquantes
                )
            )

        if donnees_heure[
            variables
        ].isna().any().any():
            raise ValueError(
                f"Valeurs manquantes dans les variables "
                f"M3 pour H={heure}."
            )

        donnees_heure[
            "prediction_MW"
        ] = modeles[
            heure
        ].predict(
            donnees_heure[
                variables
            ]
        )

        morceaux.append(
            donnees_heure
        )

    if not morceaux:
        raise ValueError(
            "Aucune prédiction M3 n'a été produite."
        )

    predictions = pd.concat(
        morceaux,
        ignore_index=True,
    )

    predictions = (
        predictions
        .sort_values(
            [
                "jour_cible",
                "heure_cible",
            ]
        )
        .reset_index(drop=True)
    )

    if predictions[
        "prediction_MW"
    ].isna().any():
        raise RuntimeError(
            "Des prédictions M3 sont manquantes."
        )

    if predictions.duplicated(
        [
            "jour_cible",
            "heure_cible",
        ]
    ).any():
        raise RuntimeError(
            "Doublons détectés dans les prédictions M3."
        )

    return predictions


# ===========================================================================
# Métriques par bloc
# ===========================================================================

def calculer_metriques_par_bloc_m3(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcule les métriques pour chaque bloc de validation.
    """

    if "bloc_validation" not in predictions.columns:
        raise ValueError(
            "La colonne bloc_validation est absente."
        )

    lignes = []

    for bloc, donnees_bloc in predictions.groupby(
        "bloc_validation",
        sort=False,
    ):

        metriques = m1.calculer_metriques(
            donnees_bloc
        )

        lignes.append(
            {
                "bloc_validation": bloc,
                "nb_observations": len(
                    donnees_bloc
                ),
                **metriques,
            }
        )

    return pd.DataFrame(
        lignes
    )


# ===========================================================================
# Validation expanding 2023
# ===========================================================================

def valider_m3_expanding(
    donnees: pd.DataFrame,
    learning_rate: float = LEARNING_RATE_M3,
    max_iter: int = MAX_ITER_M3,
    max_leaf_nodes: int = MAX_LEAF_NODES_M3,
    l2_regularization: float = L2_REGULARIZATION_M3,
) -> ResultatValidationM3:
    """
    Valide M3 sur les quatre blocs expanding de 2023.
    """

    verifier_donnees_m3(
        donnees
    )

    verifier_hyperparametres_m3(
        learning_rate=learning_rate,
        max_iter=max_iter,
        max_leaf_nodes=max_leaf_nodes,
        l2_regularization=l2_regularization,
    )

    donnees = donnees.copy()

    donnees[
        "jour_cible"
    ] = pd.to_datetime(
        donnees[
            "jour_cible"
        ]
    )

    periodes_validation = {
        "apprentissage",
        "validation",
    }

    predictions_blocs = []

    for (
        nom_bloc,
        debut_bloc,
        fin_bloc,
    ) in m1.BLOCS_VALIDATION_2023:

        debut_bloc = pd.Timestamp(
            debut_bloc
        )

        fin_bloc = pd.Timestamp(
            fin_bloc
        )

        apprentissage = m1.apprentissage_avant(
            donnees=donnees,
            debut_bloc=debut_bloc,
            periodes_autorisees=periodes_validation,
        )

        if apprentissage.empty:
            raise ValueError(
                f"Apprentissage vide pour le bloc "
                f"{nom_bloc}."
            )

        if (
            pd.to_datetime(
                apprentissage[
                    "jour_cible"
                ]
            ).max()
            >= debut_bloc
        ):
            raise RuntimeError(
                f"Fuite temporelle détectée "
                f"pour le bloc {nom_bloc}."
            )

        validation = donnees.loc[
            (
                donnees[
                    "periode"
                ] == "validation"
            )
            & (
                donnees[
                    "jour_cible"
                ] >= debut_bloc
            )
            & (
                donnees[
                    "jour_cible"
                ] < fin_bloc
            )
        ].copy()

        if validation.empty:
            raise ValueError(
                f"Bloc de validation {nom_bloc} vide."
            )

        if not (
            validation[
                "jour_cible"
            ].dt.year
            == 2023
        ).all():
            raise RuntimeError(
                "La validation M3 doit être limitée à 2023."
            )

        modeles = ajuster_modeles_m3(
            apprentissage=apprentissage,
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes,
            l2_regularization=l2_regularization,
        )

        predictions = predire_m3(
            modeles=modeles,
            donnees=validation,
        )

        predictions[
            "bloc_validation"
        ] = nom_bloc

        predictions_blocs.append(
            predictions
        )

    if not predictions_blocs:
        raise RuntimeError(
            "Aucun bloc de validation M3 produit."
        )

    predictions = pd.concat(
        predictions_blocs,
        ignore_index=True,
    )

    predictions = (
        predictions
        .sort_values(
            [
                "jour_cible",
                "heure_cible",
            ]
        )
        .reset_index(drop=True)
    )

    if len(
        predictions
    ) != 8712:
        raise RuntimeError(
            "La validation M3 2023 devrait contenir "
            f"8712 prédictions, contre "
            f"{len(predictions)} obtenues."
        )

    if predictions[
        "prediction_MW"
    ].isna().any():
        raise RuntimeError(
            "Des prédictions M3 sont manquantes."
        )

    if predictions.duplicated(
        [
            "jour_cible",
            "heure_cible",
        ]
    ).any():
        raise RuntimeError(
            "Doublons dans la validation M3."
        )

    if not (
        predictions[
            "jour_cible"
        ].dt.year
        == 2023
    ).all():
        raise RuntimeError(
            "La validation M3 contient des observations "
            "hors de l'année 2023."
        )

    metriques = m1.calculer_metriques_finales(
        predictions
    )

    metriques_blocs = (
        calculer_metriques_par_bloc_m3(
            predictions
        )
    )

    parametres = {
        "configuration": "M3-1",
        "candidat_temperature": (
            CANDIDAT_TEMPERATURE_M3
        ),
        "variante_meteo": (
            VARIANTE_METEO_M3
        ),
        "learning_rate": (
            learning_rate
        ),
        "max_iter": (
            max_iter
        ),
        "max_leaf_nodes": (
            max_leaf_nodes
        ),
        "l2_regularization": (
            l2_regularization
        ),
        "random_state": (
            RANDOM_STATE_M3
        ),
        "early_stopping": False,
    }

    return ResultatValidationM3(
        predictions=predictions,
        metriques=metriques,
        metriques_par_bloc=metriques_blocs,
        parametres=parametres,
    )


# ===========================================================================
# Test final 2024-2025
# ===========================================================================

def evaluer_m3_test_final(
    donnees: pd.DataFrame,
) -> ResultatTestFinalM3:
    """
    Évalue la configuration M3-1 gelée sur le test final 2024-2025.

    IMPORTANT
    ---------
    Cette fonction ne doit être exécutée qu'après gel définitif de M3
    sur la validation 2023.

    Le protocole est strictement identique à celui du test final M2 :

    - ré-estimation des 24 modèles au début de chaque mois ;
    - apprentissage 2016-2022 ;
    - validation 2023 ;
    - mois de test strictement antérieurs au mois prédit ;
    - aucune observation du mois courant ou du futur dans
      l'apprentissage.

    Aucun hyperparamètre n'est accepté par cette fonction afin d'éviter
    toute modification de M3 lors du test final.
    """

    verifier_configuration_m3()

    verifier_donnees_m3(
        donnees
    )

    donnees = donnees.copy()

    donnees[
        "jour_cible"
    ] = pd.to_datetime(
        donnees[
            "jour_cible"
        ]
    )

    jours = (
        donnees[
            "jour_cible"
        ]
        .dt
        .normalize()
    )

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in m1.BLOCS_TEST_FINAL_2024_2025:

        debut = pd.Timestamp(
            debut
        )

        fin = pd.Timestamp(
            fin
        )

        apprentissage = m1.apprentissage_avant(
            donnees=donnees,
            debut_bloc=debut,
            periodes_autorisees=(
                m1.PERIODES_AUTORISEES_TEST_FINAL
            ),
        )

        if apprentissage.empty:
            raise ValueError(
                f"Apprentissage vide pour le bloc "
                f"{nom_bloc}."
            )

        if (
            pd.to_datetime(
                apprentissage[
                    "jour_cible"
                ]
            ).max()
            >= debut
        ):
            raise RuntimeError(
                f"Fuite temporelle détectée "
                f"pour le bloc de test {nom_bloc}."
            )

        masque_test = (
            (
                donnees[
                    "periode"
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
            ]
            .copy()
        )

        if test_bloc.empty:
            raise ValueError(
                f"Bloc de test {nom_bloc} vide."
            )

        test_bloc[
            "bloc_test"
        ] = nom_bloc

        modeles = ajuster_modeles_m3(
            apprentissage=apprentissage,
        )

        predictions = predire_m3(
            modeles=modeles,
            donnees=test_bloc,
        )

        morceaux.append(
            predictions
        )

    if not morceaux:
        raise ValueError(
            "Aucune prédiction M3 de test final produite."
        )

    predictions = (
        pd.concat(
            morceaux,
            ignore_index=True,
        )
        .sort_values(
            [
                "jour_cible",
                "heure_cible",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # 2024 : 366 jours - 2 jours DST = 364 jours
    # 2025 : 365 jours - 2 jours DST = 363 jours
    # Total : 727 * 24 = 17 448 observations.
    if len(
        predictions
    ) != 17448:
        raise RuntimeError(
            "Le test final M3 2024-2025 devrait contenir "
            f"17448 prédictions, contre "
            f"{len(predictions)} obtenues."
        )

    if predictions[
        "prediction_MW"
    ].isna().any():
        raise RuntimeError(
            "Des prédictions M3 de test final sont manquantes."
        )

    if predictions.duplicated(
        [
            "jour_cible",
            "heure_cible",
        ]
    ).any():
        raise RuntimeError(
            "Doublons dans les prédictions finales M3."
        )

    if not predictions[
        "jour_cible"
    ].dt.year.isin(
        [
            2024,
            2025,
        ]
    ).all():
        raise RuntimeError(
            "Le test final M3 contient des observations "
            "hors de 2024-2025."
        )

    metriques = m1.calculer_metriques(
        predictions
    )

    metriques.update(
        m1.calculer_metriques_journalieres(
            predictions
        )
    )

    parametres = {
        "configuration": "M3-1",
        "candidat_temperature": (
            CANDIDAT_TEMPERATURE_M3
        ),
        "variante_meteo": (
            VARIANTE_METEO_M3
        ),
        "learning_rate": (
            LEARNING_RATE_M3
        ),
        "max_iter": (
            MAX_ITER_M3
        ),
        "max_leaf_nodes": (
            MAX_LEAF_NODES_M3
        ),
        "l2_regularization": (
            L2_REGULARIZATION_M3
        ),
        "random_state": (
            RANDOM_STATE_M3
        ),
        "early_stopping": False,
        "selection": "validation_2023",
    }

    return ResultatTestFinalM3(
        configuration="M3-1",
        candidat_temperature=(
            CANDIDAT_TEMPERATURE_M3
        ),
        variante_meteo=(
            VARIANTE_METEO_M3
        ),
        predictions=predictions,
        metriques=metriques,
        parametres=parametres,
    )


# ===========================================================================
# Résumé
# ===========================================================================

def resume_configuration_m3() -> dict[str, object]:
    """
    Retourne la configuration M3-1 gelée après validation 2023.
    """

    return {
        "configuration": "M3-1",
        "modele": (
            "HistGradientBoostingRegressor"
        ),
        "candidat_temperature": (
            CANDIDAT_TEMPERATURE_M3
        ),
        "variante_meteo": (
            VARIANTE_METEO_M3
        ),
        "learning_rate": (
            LEARNING_RATE_M3
        ),
        "max_iter": (
            MAX_ITER_M3
        ),
        "max_leaf_nodes": (
            MAX_LEAF_NODES_M3
        ),
        "l2_regularization": (
            L2_REGULARIZATION_M3
        ),
        "random_state": (
            RANDOM_STATE_M3
        ),
        "early_stopping": False,
        "selection": (
            "validation_2023"
        ),
        "critere_selection": (
            "MAE_MW"
        ),
    }