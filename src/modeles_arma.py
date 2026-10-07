"""
Modèle M4 : correction ARMA des résidus de M1.

Définition du projet
--------------------
M4 = M1 + correction ARMA des résidus de M1.

Pour chaque heure cible h, on considère la série quotidienne :

    e[d,h] = y[d,h] - y_hat_M1[d,h]

et :

    y_hat_M4[d,h]
        = y_hat_M1[d,h] + e_hat[d,h].

Disponibilité à l'origine de prévision
--------------------------------------
La prévision de la journée D est produite à 14 h le jour D-1.

Pour une heure cible h <= 13 :
    le résidu de D-1 à l'heure h est disponible.
    La correction de D est une prévision ARMA à horizon 1.

Pour une heure cible h >= 14 :
    le résidu de D-1 à l'heure h n'est pas encore disponible.
    Le dernier résidu disponible est celui de D-2.
    La correction de D est une prévision ARMA à horizon 2.

Validation
----------
Sélection exclusivement sur 2023, avec les quatre blocs
trimestriels expanding déjà utilisés pour M1.

Grille fixée avant validation :

    M4-1 : ARMA(1,0)
    M4-2 : ARMA(2,0)
    M4-3 : ARMA(1,1)
    M4-4 : ARMA(2,1)

Critère principal :
    MAE globale 2023.

Implémentation
--------------
ARMA(p,q) est estimé avec ARIMA(p,0,q) de statsmodels.

Pour éviter des milliers de réestimations inutiles :
- les paramètres ARMA sont estimés une seule fois par heure
  au début de chaque bloc ;
- les nouveaux résidus observables sont ensuite ajoutés à
  l'état du modèle avec append(..., refit=False) ;
- les paramètres restent donc gelés pendant le bloc.

Aucune donnée 2024-2025 ne doit intervenir dans la sélection M4.
"""

from __future__ import annotations

from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd

from statsmodels.tsa.arima.model import ARIMA

from src import modeles_lineaires as m1


# ===========================================================================
# Constantes
# ===========================================================================

COLONNE_JOUR = "jour_cible"
COLONNE_HEURE = "heure_cible"
COLONNE_CIBLE = "consommation_cible_MW"

COLONNE_PREDICTION_M1 = "prediction_M1_MW"
COLONNE_RESIDU_M1 = "residu_M1_MW"
COLONNE_CORRECTION_ARMA = "correction_ARMA_MW"
COLONNE_PREDICTION_M4 = "prediction_MW"

HEURE_ORIGINE = 14

MIN_OBSERVATIONS_ARMA = 30

GRILLE_M4 = {
    "M4-1": (1, 0),
    "M4-2": (2, 0),
    "M4-3": (1, 1),
    "M4-4": (2, 1),
}


# ===========================================================================
# Résultats
# ===========================================================================

@dataclass
class ResultatValidationM4:
    configuration: str
    p: int
    q: int
    predictions: pd.DataFrame
    metriques: dict[str, float]
    metriques_par_bloc: pd.DataFrame


# ===========================================================================
# Vérifications
# ===========================================================================

def verifier_configuration_m4(
    configuration: str,
) -> tuple[int, int]:
    """
    Vérifie une configuration et retourne ses ordres (p,q).
    """

    if configuration not in GRILLE_M4:
        raise ValueError(
            f"Configuration M4 inconnue : {configuration}. "
            f"Configurations autorisées : "
            f"{list(GRILLE_M4.keys())}."
        )

    return GRILLE_M4[
        configuration
    ]


def verifier_donnees_m4(
    donnees: pd.DataFrame,
) -> None:
    """
    Vérifie les données nécessaires à M4.
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
            "Le DataFrame M4 est vide."
        )

    m1.verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            m1.COLONNE_COVID,
            m1.COLONNE_PERIODE,
        ],
    )


# ===========================================================================
# ARMA
# ===========================================================================

def ajuster_arma(
    residus: pd.Series,
    p: int,
    q: int,
):
    """
    Ajuste ARMA(p,q) via ARIMA(p,0,q).
    """

    serie = (
        pd.Series(
            residus,
            dtype=float,
        )
        .dropna()
        .reset_index(
            drop=True
        )
    )

    if len(
        serie
    ) < MIN_OBSERVATIONS_ARMA:
        raise ValueError(
            "Pas assez d'observations pour ARMA : "
            f"{len(serie)}."
        )

    if not np.isfinite(
        serie.to_numpy()
    ).all():
        raise ValueError(
            "Valeurs non finies dans les résidus ARMA."
        )

    with warnings.catch_warnings():

        warnings.simplefilter(
            "ignore"
        )

        modele = ARIMA(
            serie.to_numpy(),
            order=(
                p,
                0,
                q,
            ),
            trend="c",
            enforce_stationarity=True,
            enforce_invertibility=True,
        )

        resultat = modele.fit()

    return resultat


def forecast_arma(
    resultat,
    horizon: int,
) -> float:
    """
    Retourne la prévision ARMA au dernier pas de l'horizon.
    """

    if horizon < 1:
        raise ValueError(
            "horizon doit être >= 1."
        )

    previsions = np.asarray(
        resultat.forecast(
            steps=horizon
        ),
        dtype=float,
    )

    correction = float(
        previsions[
            horizon - 1
        ]
    )

    if not np.isfinite(
        correction
    ):
        raise RuntimeError(
            "Correction ARMA non finie."
        )

    return correction


# ===========================================================================
# Prédictions et résidus M1
# ===========================================================================

def construire_predictions_m1(
    modeles_m1,
    donnees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produit les prédictions M1 et calcule les résidus.
    """

    predictions = m1.predire_m1(
        modeles_m1,
        donnees,
    )

    predictions = predictions.rename(
        columns={
            "prediction_MW": (
                COLONNE_PREDICTION_M1
            )
        }
    )

    predictions[
        COLONNE_JOUR
    ] = pd.to_datetime(
        predictions[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    predictions[
        COLONNE_RESIDU_M1
    ] = (
        predictions[
            COLONNE_CIBLE
        ]
        - predictions[
            COLONNE_PREDICTION_M1
        ]
    )

    if predictions[
        COLONNE_RESIDU_M1
    ].isna().any():
        raise RuntimeError(
            "NaN dans les résidus M1."
        )

    return predictions


# ===========================================================================
# Historique disponible
# ===========================================================================

def dernier_jour_disponible(
    jour_cible: pd.Timestamp,
    heure_cible: int,
) -> pd.Timestamp:
    """
    Retourne le dernier jour dont le résidu de l'heure considérée
    est observable à l'origine de prévision.

    Cible D, origine D-1 à 14 h :

    H <= 13 : D-1 disponible.
    H >= 14 : D-2 disponible.
    """

    jour_cible = pd.Timestamp(
        jour_cible
    ).normalize()

    if heure_cible < HEURE_ORIGINE:
        return (
            jour_cible
            - pd.Timedelta(
                days=1
            )
        )

    return (
        jour_cible
        - pd.Timedelta(
            days=2
        )
    )


def horizon_arma(
    heure_cible: int,
) -> int:
    """
    Horizon ARMA opérationnel pour une heure cible.
    """

    if heure_cible < 0 or heure_cible > 23:
        raise ValueError(
            "heure_cible doit être comprise entre 0 et 23."
        )

    if heure_cible < HEURE_ORIGINE:
        return 1

    return 2


# ===========================================================================
# Prédiction rapide d'une heure
# ===========================================================================

def predire_heure_m4(
    residus_historiques: pd.DataFrame,
    residus_bloc: pd.DataFrame,
    heure: int,
    p: int,
    q: int,
) -> pd.DataFrame:
    """
    Produit les corrections ARMA pour une heure donnée.

    Les paramètres ARMA sont estimés une seule fois au début du bloc.
    L'état est ensuite mis à jour avec les nouveaux résidus réellement
    observables, sans réestimation des paramètres.
    """

    historique_h = (
        residus_historiques.loc[
            residus_historiques[
                COLONNE_HEURE
            ] == heure,
            [
                COLONNE_JOUR,
                COLONNE_RESIDU_M1,
            ],
        ]
        .copy()
        .sort_values(
            COLONNE_JOUR
        )
        .reset_index(
            drop=True
        )
    )

    bloc_h = (
        residus_bloc.loc[
            residus_bloc[
                COLONNE_HEURE
            ] == heure
        ]
        .copy()
        .sort_values(
            COLONNE_JOUR
        )
        .reset_index(
            drop=True
        )
    )

    if historique_h.empty:
        raise ValueError(
            f"Historique résiduel vide pour H={heure}."
        )

    if bloc_h.empty:
        raise ValueError(
            f"Bloc vide pour H={heure}."
        )

    premier_jour = pd.Timestamp(
        bloc_h[
            COLONNE_JOUR
        ].iloc[0]
    ).normalize()

    cutoff_initial = (
        dernier_jour_disponible(
            jour_cible=premier_jour,
            heure_cible=heure,
        )
    )

    # Important :
    # pour H >= 14, le dernier jour de l'échantillon M1 peut exister
    # dans les données mais son résidu n'est pas encore observable
    # à l'origine de la première prévision.
    historique_initial = (
        historique_h.loc[
            historique_h[
                COLONNE_JOUR
            ]
            <= cutoff_initial
        ]
        .copy()
    )

    if len(
        historique_initial
    ) < MIN_OBSERVATIONS_ARMA:
        raise ValueError(
            f"Historique ARMA insuffisant pour H={heure} : "
            f"{len(historique_initial)} observations."
        )

    resultat_arma = ajuster_arma(
        residus=historique_initial[
            COLONNE_RESIDU_M1
        ],
        p=p,
        q=q,
    )

    dernier_jour_integre = pd.Timestamp(
        historique_initial[
            COLONNE_JOUR
        ].max()
    ).normalize()

    # Ensemble de tous les résidus connus ou qui deviendront connus
    # pendant le bloc.
    disponibles = pd.concat(
        [
            historique_h,
            bloc_h[
                [
                    COLONNE_JOUR,
                    COLONNE_RESIDU_M1,
                ]
            ],
        ],
        ignore_index=True,
    )

    disponibles = (
        disponibles
        .drop_duplicates(
            subset=[
                COLONNE_JOUR
            ],
            keep="last",
        )
        .sort_values(
            COLONNE_JOUR
        )
        .reset_index(
            drop=True
        )
    )

    corrections = []

    for ligne in bloc_h.itertuples(
        index=False
    ):

        jour = pd.Timestamp(
            getattr(
                ligne,
                COLONNE_JOUR,
            )
        ).normalize()

        cutoff = dernier_jour_disponible(
            jour_cible=jour,
            heure_cible=heure,
        )

        # Ajout des nouveaux résidus devenus observables depuis
        # la prévision précédente.
        nouveaux = (
            disponibles.loc[
                (
                    disponibles[
                        COLONNE_JOUR
                    ]
                    > dernier_jour_integre
                )
                & (
                    disponibles[
                        COLONNE_JOUR
                    ]
                    <= cutoff
                ),
                [
                    COLONNE_JOUR,
                    COLONNE_RESIDU_M1,
                ],
            ]
            .sort_values(
                COLONNE_JOUR
            )
        )

        if not nouveaux.empty:

            nouvelles_valeurs = (
                nouveaux[
                    COLONNE_RESIDU_M1
                ]
                .astype(float)
                .to_numpy()
            )

            resultat_arma = (
                resultat_arma.append(
                    nouvelles_valeurs,
                    refit=False,
                )
            )

            dernier_jour_integre = (
                pd.Timestamp(
                    nouveaux[
                        COLONNE_JOUR
                    ].max()
                ).normalize()
            )

        correction = forecast_arma(
            resultat=resultat_arma,
            horizon=horizon_arma(
                heure
            ),
        )

        corrections.append(
            correction
        )

    resultat = bloc_h.copy()

    resultat[
        COLONNE_CORRECTION_ARMA
    ] = corrections

    return resultat


# ===========================================================================
# Prédiction d'un bloc
# ===========================================================================

def predire_bloc_m4(
    apprentissage: pd.DataFrame,
    bloc: pd.DataFrame,
    p: int,
    q: int,
) -> pd.DataFrame:
    """
    Prédit un bloc M4 complet.

    M1 est ajusté une fois sur l'échantillon strictement antérieur
    au bloc.

    Les 24 ARMA sont ensuite estimés sur les résidus M1 disponibles
    à l'origine de la première prévision du bloc.
    """

    if apprentissage.empty:
        raise ValueError(
            "Apprentissage M4 vide."
        )

    if bloc.empty:
        raise ValueError(
            "Bloc M4 vide."
        )

    apprentissage = (
        apprentissage.copy()
    )

    bloc = bloc.copy()

    apprentissage[
        COLONNE_JOUR
    ] = pd.to_datetime(
        apprentissage[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    bloc[
        COLONNE_JOUR
    ] = pd.to_datetime(
        bloc[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    # -----------------------------------------------------------------------
    # M1
    # -----------------------------------------------------------------------

    modeles_m1 = (
        m1.ajuster_modeles_m1(
            apprentissage
        )
    )

    predictions_apprentissage = (
        construire_predictions_m1(
            modeles_m1=modeles_m1,
            donnees=apprentissage,
        )
    )

    predictions_bloc = (
        construire_predictions_m1(
            modeles_m1=modeles_m1,
            donnees=bloc,
        )
    )

    residus_historiques = (
        predictions_apprentissage[
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
                COLONNE_RESIDU_M1,
            ]
        ]
        .copy()
    )

    residus_bloc = (
        predictions_bloc[
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
                COLONNE_CIBLE,
                COLONNE_PREDICTION_M1,
                COLONNE_RESIDU_M1,
            ]
        ]
        .copy()
    )

    # -----------------------------------------------------------------------
    # ARMA par heure
    # -----------------------------------------------------------------------

    morceaux = []

    for heure in range(24):

        predictions_h = (
            predire_heure_m4(
                residus_historiques=(
                    residus_historiques
                ),
                residus_bloc=residus_bloc,
                heure=heure,
                p=p,
                q=q,
            )
        )

        morceaux.append(
            predictions_h
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

    predictions[
        COLONNE_PREDICTION_M4
    ] = (
        predictions[
            COLONNE_PREDICTION_M1
        ]
        + predictions[
            COLONNE_CORRECTION_ARMA
        ]
    )

    if predictions[
        COLONNE_PREDICTION_M4
    ].isna().any():
        raise RuntimeError(
            "NaN dans les prédictions M4."
        )

    if not np.isfinite(
        predictions[
            COLONNE_PREDICTION_M4
        ].to_numpy()
    ).all():
        raise RuntimeError(
            "Valeurs non finies dans les prédictions M4."
        )

    if predictions.duplicated(
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
        ]
    ).any():
        raise RuntimeError(
            "Doublons jour/heure dans M4."
        )

    return predictions


# ===========================================================================
# Métriques par bloc
# ===========================================================================

def calculer_metriques_par_bloc_m4(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcule les métriques M4 pour chaque bloc 2023.
    """

    if "bloc_validation" not in predictions.columns:
        raise ValueError(
            "bloc_validation absent."
        )

    lignes = []

    for (
        bloc,
        donnees_bloc,
    ) in predictions.groupby(
        "bloc_validation",
        sort=False,
    ):

        metriques = (
            m1.calculer_metriques(
                donnees_bloc
            )
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
# Validation 2023
# ===========================================================================

def valider_m4_expanding(
    donnees: pd.DataFrame,
    configuration: str,
) -> ResultatValidationM4:
    """
    Validation expanding M4 sur 2023.

    Aucune observation 2024-2025 n'est utilisée.
    """

    verifier_donnees_m4(
        donnees
    )

    p, q = verifier_configuration_m4(
        configuration
    )

    donnees = donnees.copy()

    donnees[
        COLONNE_JOUR
    ] = pd.to_datetime(
        donnees[
            COLONNE_JOUR
        ]
    ).dt.normalize()

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in m1.BLOCS_VALIDATION_2023:

        debut = pd.Timestamp(
            debut
        ).normalize()

        fin = pd.Timestamp(
            fin
        ).normalize()

        apprentissage = (
            m1.apprentissage_avant(
                donnees,
                debut,
                periodes_autorisees=(
                    m1
                    .PERIODES_AUTORISEES_VALIDATION_EXPANDING
                ),
            )
        )

        if apprentissage.empty:
            raise ValueError(
                f"Apprentissage vide pour {nom_bloc}."
            )

        if (
            pd.to_datetime(
                apprentissage[
                    COLONNE_JOUR
                ]
            ).max()
            >= debut
        ):
            raise RuntimeError(
                f"Fuite temporelle détectée pour {nom_bloc}."
            )

        masque = (
            (
                donnees[
                    m1.COLONNE_PERIODE
                ]
                == "validation"
            )
            & (
                donnees[
                    COLONNE_JOUR
                ]
                >= debut
            )
            & (
                donnees[
                    COLONNE_JOUR
                ]
                < fin
            )
        )

        validation_bloc = (
            donnees.loc[
                masque
            ].copy()
        )

        if validation_bloc.empty:
            raise ValueError(
                f"Bloc {nom_bloc} vide."
            )

        predictions = (
            predire_bloc_m4(
                apprentissage=apprentissage,
                bloc=validation_bloc,
                p=p,
                q=q,
            )
        )

        predictions[
            "bloc_validation"
        ] = nom_bloc

        morceaux.append(
            predictions
        )

    if not morceaux:
        raise RuntimeError(
            "Aucune prédiction M4 produite."
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

    if len(
        predictions
    ) != 8712:
        raise RuntimeError(
            "La validation M4 2023 doit contenir "
            f"8712 prédictions, contre "
            f"{len(predictions)}."
        )

    if predictions[
        COLONNE_PREDICTION_M4
    ].isna().any():
        raise RuntimeError(
            "NaN dans les prédictions M4."
        )

    if predictions.duplicated(
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
        ]
    ).any():
        raise RuntimeError(
            "Doublons dans la validation M4."
        )

    annees = set(
        predictions[
            COLONNE_JOUR
        ].dt.year.unique()
    )

    if annees != {
        2023
    }:
        raise RuntimeError(
            f"Années inattendues : {annees}."
        )

    metriques = (
        m1.calculer_metriques_finales(
            predictions
        )
    )

    metriques_par_bloc = (
        calculer_metriques_par_bloc_m4(
            predictions
        )
    )

    return ResultatValidationM4(
        configuration=configuration,
        p=p,
        q=q,
        predictions=predictions,
        metriques=metriques,
        metriques_par_bloc=metriques_par_bloc,
    )


# ===========================================================================
# Grille
# ===========================================================================

def resume_grille_m4() -> pd.DataFrame:
    """
    Retourne la grille M4 fixée avant validation.
    """

    lignes = []

    for (
        configuration,
        (p, q),
    ) in GRILLE_M4.items():

        lignes.append(
            {
                "configuration": configuration,
                "p": p,
                "q": q,
                "modele": f"ARMA({p},{q})",
                "base": "M1",
            }
        )

    return pd.DataFrame(
        lignes
    )