"""
Tests du modèle M3 basé sur HistGradientBoostingRegressor.

Les tests vérifient principalement :

- la configuration gelée héritée de M2 ;
- l'identité des variables M2-F / M3 ;
- la règle LAG-B selon l'heure cible ;
- la construction du pipeline HGBR ;
- la validation des hyperparamètres ;
- les protections contre la météo parfaite ;
- l'apprentissage et la prédiction ;
- la reproductibilité ;
- l'absence de fuite vers la période de test.

Les tests lourds de validation expanding complète sur 2023 ne sont
volontairement pas exécutés ici.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline

from src import modeles_hgbr as m3
from src import modeles_meteo as m2


# ===========================================================================
# Dataset synthétique
# ===========================================================================

def dataset_test_m3(
    n_jours: int = 120,
) -> pd.DataFrame:
    """
    Construit un petit dataset synthétique compatible avec M3.

    Les valeurs n'ont pas de signification physique particulière.
    Elles servent uniquement aux tests structurels et fonctionnels.
    """

    rng = np.random.default_rng(
        42
    )

    dates = pd.date_range(
        "2021-01-01",
        periods=n_jours,
        freq="D",
    )

    lignes = []

    for indice_jour, jour in enumerate(
        dates
    ):
        for heure in range(24):

            base = (
                45000.0
                + 5000.0
                * np.sin(
                    2.0
                    * np.pi
                    * heure
                    / 24.0
                )
            )

            temperature = (
                10.0
                + 6.0
                * np.sin(
                    2.0
                    * np.pi
                    * indice_jour
                    / 365.0
                )
            )

            consommation = (
                base
                - 300.0 * temperature
                + rng.normal(
                    0.0,
                    100.0,
                )
            )

            ligne = {
                "jour_cible": jour,
                "heure_cible": heure,
                "consommation_cible_MW": consommation,
                "periode": "apprentissage",
                "exclu_covid": False,
                "jour_semaine": jour.dayofweek,
                "mois": jour.month,
                "ferie": 0,
                "veille_ferie": 0,
                "lendemain_ferie": 0,
                "pont_potentiel": 0,
                "vacances_A": 0,
                "vacances_B": 0,
                "vacances_C": 0,
                "conso_veille_effective_MW": (
                    consommation
                    + rng.normal(
                        0.0,
                        300.0,
                    )
                ),
                "conso_lag48_MW": (
                    consommation
                    + rng.normal(
                        0.0,
                        500.0,
                    )
                ),
                "conso_lag168_MW": (
                    consommation
                    + rng.normal(
                        0.0,
                        700.0,
                    )
                ),
                "temp_38_ponderee_origine": (
                    temperature
                ),
                "temp_38_ponderee_veille": (
                    temperature
                    + rng.normal(
                        0.0,
                        0.5,
                    )
                ),
                "temp_38_ponderee_lissee": (
                    temperature
                    + rng.normal(
                        0.0,
                        0.3,
                    )
                ),
                (
                    "temp_38_ponderee_"
                    "degres_chauffage_origine"
                ): max(
                    0.0,
                    18.0 - temperature,
                ),
                (
                    "temp_38_ponderee_"
                    "degres_chauffage_lisses"
                ): max(
                    0.0,
                    18.0 - temperature,
                ),
                (
                    "temp_38_ponderee_"
                    "degres_climatisation_origine"
                ): max(
                    0.0,
                    temperature - 22.0,
                ),
                (
                    "temp_38_ponderee_"
                    "degres_climatisation_lisses"
                ): max(
                    0.0,
                    temperature - 22.0,
                ),
            }

            lignes.append(
                ligne
            )

    return pd.DataFrame(
        lignes
    )


# ===========================================================================
# Configuration
# ===========================================================================

def test_configuration_m3_gelee():
    assert (
        m3.CANDIDAT_TEMPERATURE_M3
        == "temp_38_ponderee"
    )

    assert (
        m3.VARIANTE_METEO_M3
        == "M2-F"
    )

    assert (
        m3.RANDOM_STATE_M3
        == 42
    )


def test_resume_configuration_m3():
    configuration = (
        m3.resume_configuration_m3()
    )

    assert (
        configuration["modele"]
        == "HistGradientBoostingRegressor"
    )

    assert (
        configuration[
            "candidat_temperature"
        ]
        == "temp_38_ponderee"
    )

    assert (
        configuration[
            "variante_meteo"
        ]
        == "M2-F"
    )

    assert (
        configuration[
            "random_state"
        ]
        == 42
    )

    assert (
        configuration[
            "early_stopping"
        ]
        is False
    )


# ===========================================================================
# Variables
# ===========================================================================

@pytest.mark.parametrize(
    "heure",
    list(range(24)),
)
def test_variables_m3_identiques_m2(
    heure,
):
    variables_m2 = (
        m2.variables_m2(
            heure=heure,
            candidat="temp_38_ponderee",
            variante="M2-F",
        )
    )

    variables_m3 = (
        m3.variables_m3(
            heure
        )
    )

    assert (
        variables_m3
        == variables_m2
    )


@pytest.mark.parametrize(
    "heure",
    list(range(24)),
)
def test_variables_numeriques_m3_identiques_m2(
    heure,
):
    variables_m2 = (
        m2.variables_numeriques_m2(
            heure=heure,
            candidat="temp_38_ponderee",
            variante="M2-F",
        )
    )

    variables_m3 = (
        m3.variables_numeriques_m3(
            heure
        )
    )

    assert (
        variables_m3
        == variables_m2
    )


@pytest.mark.parametrize(
    "heure",
    list(range(13)),
)
def test_retard_effectif_present_jusqua_12h(
    heure,
):
    assert (
        "conso_veille_effective_MW"
        in m3.variables_m3(
            heure
        )
    )


@pytest.mark.parametrize(
    "heure",
    list(range(13, 24)),
)
def test_retard_effectif_absent_apres_12h(
    heure,
):
    assert (
        "conso_veille_effective_MW"
        not in m3.variables_m3(
            heure
        )
    )


@pytest.mark.parametrize(
    "heure",
    list(range(24)),
)
def test_lag48_et_lag168_toujours_presents(
    heure,
):
    variables = (
        m3.variables_m3(
            heure
        )
    )

    assert (
        "conso_lag48_MW"
        in variables
    )

    assert (
        "conso_lag168_MW"
        in variables
    )


@pytest.mark.parametrize(
    "heure",
    [0, 6, 12, 13, 18, 23],
)
def test_variables_meteo_m2f_presentes(
    heure,
):
    variables = set(
        m3.variables_m3(
            heure
        )
    )

    meteo = set(
        m2.variables_meteo_m2(
            candidat="temp_38_ponderee",
            variante="M2-F",
        )
    )

    assert meteo.issubset(
        variables
    )

    assert len(
        meteo
    ) == 7


# ===========================================================================
# Hyperparamètres
# ===========================================================================

@pytest.mark.parametrize(
    "learning_rate",
    [
        0.0,
        -0.1,
    ],
)
def test_learning_rate_invalide(
    learning_rate,
):
    with pytest.raises(
        ValueError
    ):
        m3.verifier_hyperparametres_m3(
            learning_rate=learning_rate,
            max_iter=100,
            max_leaf_nodes=31,
            l2_regularization=1.0,
        )


@pytest.mark.parametrize(
    "max_iter",
    [
        0,
        -1,
    ],
)
def test_max_iter_invalide(
    max_iter,
):
    with pytest.raises(
        ValueError
    ):
        m3.verifier_hyperparametres_m3(
            learning_rate=0.05,
            max_iter=max_iter,
            max_leaf_nodes=31,
            l2_regularization=1.0,
        )


@pytest.mark.parametrize(
    "max_leaf_nodes",
    [
        0,
        1,
        -1,
    ],
)
def test_max_leaf_nodes_invalide(
    max_leaf_nodes,
):
    with pytest.raises(
        ValueError
    ):
        m3.verifier_hyperparametres_m3(
            learning_rate=0.05,
            max_iter=100,
            max_leaf_nodes=max_leaf_nodes,
            l2_regularization=1.0,
        )


def test_l2_negative_invalide():
    with pytest.raises(
        ValueError
    ):
        m3.verifier_hyperparametres_m3(
            learning_rate=0.05,
            max_iter=100,
            max_leaf_nodes=31,
            l2_regularization=-1.0,
        )


def test_hyperparametres_valides():
    m3.verifier_hyperparametres_m3(
        learning_rate=0.05,
        max_iter=100,
        max_leaf_nodes=31,
        l2_regularization=1.0,
    )


# ===========================================================================
# Pipeline
# ===========================================================================

@pytest.mark.parametrize(
    "heure",
    [
        0,
        10,
        13,
        23,
    ],
)
def test_construire_modele_m3(
    heure,
):
    modele = (
        m3.construire_modele_m3(
            heure
        )
    )

    assert isinstance(
        modele,
        Pipeline,
    )

    assert (
        "preparation"
        in modele.named_steps
    )

    assert (
        "regression"
        in modele.named_steps
    )

    regression = (
        modele.named_steps[
            "regression"
        ]
    )

    assert isinstance(
        regression,
        HistGradientBoostingRegressor,
    )

    assert (
        regression.random_state
        == 42
    )

    assert (
        regression.early_stopping
        is False
    )


@pytest.mark.parametrize(
    "heure",
    [
        -1,
        24,
        25,
    ],
)
def test_heure_invalide(
    heure,
):
    with pytest.raises(
        ValueError
    ):
        m3.construire_modele_m3(
            heure
        )


def test_hyperparametres_transmis_au_modele():
    modele = (
        m3.construire_modele_m3(
            heure=10,
            learning_rate=0.1,
            max_iter=75,
            max_leaf_nodes=15,
            l2_regularization=2.5,
        )
    )

    regression = (
        modele.named_steps[
            "regression"
        ]
    )

    assert (
        regression.learning_rate
        == 0.1
    )

    assert (
        regression.max_iter
        == 75
    )

    assert (
        regression.max_leaf_nodes
        == 15
    )

    assert (
        regression.l2_regularization
        == 2.5
    )


# ===========================================================================
# Vérification des données
# ===========================================================================

def test_dataframe_vide_refuse():
    with pytest.raises(
        ValueError
    ):
        m3.verifier_donnees_m3(
            pd.DataFrame()
        )


def test_objet_non_dataframe_refuse():
    with pytest.raises(
        TypeError
    ):
        m3.verifier_donnees_m3(
            []
        )


def test_colonne_obligatoire_manquante():
    donnees = (
        dataset_test_m3(
            n_jours=3
        )
    )

    donnees = donnees.drop(
        columns=[
            "periode"
        ]
    )

    with pytest.raises(
        ValueError
    ):
        m3.verifier_donnees_m3(
            donnees
        )


def test_meteo_parfaite_refusee():
    donnees = (
        dataset_test_m3(
            n_jours=3
        )
    )

    donnees[
        "temp_38_ponderee_meteo_parfaite"
    ] = 10.0

    with pytest.raises(
        ValueError
    ):
        m3.verifier_donnees_m3(
            donnees
        )


# ===========================================================================
# Apprentissage
# ===========================================================================

def test_ajuster_24_modeles():
    donnees = (
        dataset_test_m3(
            n_jours=80
        )
    )

    modeles = (
        m3.ajuster_modeles_m3(
            apprentissage=donnees,
            max_iter=10,
            max_leaf_nodes=7,
        )
    )

    assert set(
        modeles.keys()
    ) == set(
        range(24)
    )

    assert len(
        modeles
    ) == 24


def test_prediction_complete():
    donnees = (
        dataset_test_m3(
            n_jours=80
        )
    )

    apprentissage = donnees.loc[
        donnees[
            "jour_cible"
        ]
        < pd.Timestamp(
            "2021-03-01"
        )
    ].copy()

    validation = donnees.loc[
        donnees[
            "jour_cible"
        ]
        >= pd.Timestamp(
            "2021-03-01"
        )
    ].copy()

    modeles = (
        m3.ajuster_modeles_m3(
            apprentissage=apprentissage,
            max_iter=10,
            max_leaf_nodes=7,
        )
    )

    predictions = (
        m3.predire_m3(
            modeles=modeles,
            donnees=validation,
        )
    )

    assert len(
        predictions
    ) == len(
        validation
    )

    assert not predictions[
        "prediction_MW"
    ].isna().any()

    assert not predictions.duplicated(
        [
            "jour_cible",
            "heure_cible",
        ]
    ).any()


def test_prediction_reproductible():
    donnees = (
        dataset_test_m3(
            n_jours=80
        )
    )

    apprentissage = donnees.loc[
        donnees[
            "jour_cible"
        ]
        < pd.Timestamp(
            "2021-03-01"
        )
    ].copy()

    validation = donnees.loc[
        donnees[
            "jour_cible"
        ]
        >= pd.Timestamp(
            "2021-03-01"
        )
    ].copy()

    modeles_1 = (
        m3.ajuster_modeles_m3(
            apprentissage=apprentissage,
            max_iter=10,
            max_leaf_nodes=7,
        )
    )

    modeles_2 = (
        m3.ajuster_modeles_m3(
            apprentissage=apprentissage,
            max_iter=10,
            max_leaf_nodes=7,
        )
    )

    predictions_1 = (
        m3.predire_m3(
            modeles=modeles_1,
            donnees=validation,
        )[
            "prediction_MW"
        ].to_numpy()
    )

    predictions_2 = (
        m3.predire_m3(
            modeles=modeles_2,
            donnees=validation,
        )[
            "prediction_MW"
        ].to_numpy()
    )

    np.testing.assert_allclose(
        predictions_1,
        predictions_2,
        rtol=0.0,
        atol=0.0,
    )


# ===========================================================================
# Protections supplémentaires
# ===========================================================================

def test_prediction_refuse_dictionnaire_incomplet():
    donnees = (
        dataset_test_m3(
            n_jours=3
        )
    )

    with pytest.raises(
        ValueError
    ):
        m3.predire_m3(
            modeles={},
            donnees=donnees,
        )


def test_nan_variable_apprentissage_refuse():
    donnees = (
        dataset_test_m3(
            n_jours=10
        )
    )

    donnees.loc[
        donnees.index[0],
        "conso_lag48_MW",
    ] = np.nan

    with pytest.raises(
        ValueError
    ):
        m3.ajuster_modeles_m3(
            apprentissage=donnees,
            max_iter=5,
        )


def test_nan_cible_apprentissage_refuse():
    donnees = (
        dataset_test_m3(
            n_jours=10
        )
    )

    donnees.loc[
        donnees.index[0],
        "consommation_cible_MW",
    ] = np.nan

    with pytest.raises(
        ValueError
    ):
        m3.ajuster_modeles_m3(
            apprentissage=donnees,
            max_iter=5,
        )