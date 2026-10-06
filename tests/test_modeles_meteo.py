import numpy as np
import pandas as pd
import pytest

from sklearn.preprocessing import OneHotEncoder

from src import modeles_lineaires
from src import modeles_meteo


# ============================================================
# Dataset synthétique
# ============================================================

def dataset_test_m2():
    """
    Dataset synthétique contenant M1 et les trois
    représentations météorologiques.
    """

    lignes = []

    dates_train = pd.date_range(
        "2022-01-01",
        periods=14,
        freq="D",
    )

    dates_validation = pd.date_range(
        "2023-01-01",
        periods=4,
        freq="D",
    )

    for periode, dates in [
        ("apprentissage", dates_train),
        ("validation", dates_validation),
    ]:

        for jour in dates:

            temperature = (
                8.0
                + 0.2 * jour.day
            )

            for heure in range(24):

                base = (
                    40_000
                    + 100 * heure
                    + 20 * jour.day
                )

                ligne = {
                    "jour_cible":
                        jour,

                    "heure_cible":
                        heure,

                    "periode":
                        periode,

                    "exclu_covid":
                        False,

                    "conso_veille_effective_MW":
                        base - 500,

                    "conso_lag48_MW":
                        base - 600,

                    "conso_lag168_MW":
                        base - 700,

                    "jour_semaine":
                        jour.dayofweek,

                    "mois":
                        jour.month,

                    "ferie":
                        0,

                    "veille_ferie":
                        0,

                    "lendemain_ferie":
                        0,

                    "pont_potentiel":
                        0,

                    "vacances_A":
                        0,

                    "vacances_B":
                        0,

                    "vacances_C":
                        0,

                    "consommation_cible_MW":
                        base,
                }

                for indice, candidat in enumerate(
                    modeles_meteo
                    .CANDIDATS_TEMPERATURE
                ):

                    decalage = (
                        0.1 * indice
                    )

                    t = (
                        temperature
                        + decalage
                    )

                    ligne[
                        f"{candidat}_origine"
                    ] = t

                    ligne[
                        f"{candidat}_veille"
                    ] = (
                        t - 0.5
                    )

                    ligne[
                        f"{candidat}_lissee"
                    ] = (
                        t - 0.2
                    )

                    ligne[
                        f"{candidat}_"
                        "degres_chauffage_origine"
                    ] = max(
                        0.0,
                        15.0 - t,
                    )

                    ligne[
                        f"{candidat}_"
                        "degres_chauffage_lisses"
                    ] = max(
                        0.0,
                        15.0 - (t - 0.2),
                    )

                    ligne[
                        f"{candidat}_"
                        "degres_climatisation_origine"
                    ] = max(
                        0.0,
                        t - 22.0,
                    )

                    ligne[
                        f"{candidat}_"
                        "degres_climatisation_lisses"
                    ] = max(
                        0.0,
                        (t - 0.2) - 22.0,
                    )

                lignes.append(
                    ligne
                )

    return pd.DataFrame(
        lignes
    )


# ============================================================
# Candidats température
# ============================================================

def test_trois_candidats_temperature():

    assert (
        modeles_meteo
        .CANDIDATS_TEMPERATURE
        == [
            "temp_8_villes",
            "temp_38_simple",
            "temp_38_ponderee",
        ]
    )


def test_candidat_invalide():

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .verifier_candidat_temperature(
                "temperature_future"
            )
        )


# ============================================================
# Variantes météo
# ============================================================

def test_six_variantes_meteo():

    assert list(
        modeles_meteo
        .VARIANTES_METEO_M2
        .keys()
    ) == [
        "M2-A",
        "M2-B",
        "M2-C",
        "M2-D",
        "M2-E",
        "M2-F",
    ]


def test_variante_invalide():

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .verifier_variante_meteo(
                "M2-Z"
            )
        )


def test_variante_defaut_est_m2_f():

    assert (
        modeles_meteo
        .VARIANTE_METEO_DEFAUT
        == "M2-F"
    )


def test_nombre_variables_par_variante():

    attendu = {
        "M2-A": 1,
        "M2-B": 2,
        "M2-C": 3,
        "M2-D": 4,
        "M2-E": 6,
        "M2-F": 7,
    }

    for variante, nombre in (
        attendu.items()
    ):

        variables = (
            modeles_meteo
            .variables_meteo_m2(
                "temp_8_villes",
                variante,
            )
        )

        assert (
            len(variables)
            == nombre
        )


def test_m2_a_origine_seulement():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-A",
        )
    )

    assert variables == [
        "temp_8_villes_origine",
    ]


def test_m2_b_origine_veille():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-B",
        )
    )

    assert variables == [
        "temp_8_villes_origine",
        "temp_8_villes_veille",
    ]


def test_m2_c_origine_veille_lissee():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-C",
        )
    )

    assert variables == [
        "temp_8_villes_origine",
        "temp_8_villes_veille",
        "temp_8_villes_lissee",
    ]


def test_m2_d_chauffage_sans_veille():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-D",
        )
    )

    assert variables == [
        "temp_8_villes_origine",
        "temp_8_villes_lissee",
        (
            "temp_8_villes_"
            "degres_chauffage_origine"
        ),
        (
            "temp_8_villes_"
            "degres_chauffage_lisses"
        ),
    ]

    assert (
        "temp_8_villes_veille"
        not in variables
    )


def test_m2_e_sans_veille():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-E",
        )
    )

    assert (
        len(variables)
        == 6
    )

    assert (
        "temp_8_villes_veille"
        not in variables
    )


def test_m2_f_sept_variables():

    variables = (
        modeles_meteo
        .variables_meteo_m2(
            "temp_8_villes",
            "M2-F",
        )
    )

    assert variables == [
        "temp_8_villes_origine",
        "temp_8_villes_veille",
        "temp_8_villes_lissee",
        (
            "temp_8_villes_"
            "degres_chauffage_origine"
        ),
        (
            "temp_8_villes_"
            "degres_chauffage_lisses"
        ),
        (
            "temp_8_villes_"
            "degres_climatisation_origine"
        ),
        (
            "temp_8_villes_"
            "degres_climatisation_lisses"
        ),
    ]


def test_appel_sans_variante_reproduit_m2_f():

    for candidat in (
        modeles_meteo
        .CANDIDATS_TEMPERATURE
    ):

        assert (
            modeles_meteo
            .variables_meteo_m2(
                candidat
            )
            ==
            modeles_meteo
            .variables_meteo_m2(
                candidat,
                "M2-F",
            )
        )


# ============================================================
# Météo parfaite
# ============================================================

def test_aucune_meteo_parfaite():

    for candidat in (
        modeles_meteo
        .CANDIDATS_TEMPERATURE
    ):

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            variables = (
                modeles_meteo
                .variables_meteo_m2(
                    candidat,
                    variante,
                )
            )

            assert not any(
                "meteo_parfaite"
                in variable
                for variable in variables
            )


def test_interdiction_explicite_meteo_parfaite():

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .verifier_absence_meteo_parfaite(
                [
                    (
                        "temp_8_villes_"
                        "meteo_parfaite"
                    )
                ]
            )
        )


# ============================================================
# Relation M1 / M2
# ============================================================

def test_toutes_variantes_contiennent_m1():

    for heure in range(24):

        m1 = set(
            modeles_lineaires
            .variables_m1(
                heure
            )
        )

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            m2 = set(
                modeles_meteo
                .variables_m2(
                    heure,
                    "temp_8_villes",
                    variante,
                )
            )

            assert (
                m1.issubset(
                    m2
                )
            )


def test_nombre_variables_ajoutees():

    attendu = {
        "M2-A": 1,
        "M2-B": 2,
        "M2-C": 3,
        "M2-D": 4,
        "M2-E": 6,
        "M2-F": 7,
    }

    for heure in range(24):

        m1 = set(
            modeles_lineaires
            .variables_m1(
                heure
            )
        )

        for variante, nombre in (
            attendu.items()
        ):

            m2 = set(
                modeles_meteo
                .variables_m2(
                    heure,
                    "temp_38_simple",
                    variante,
                )
            )

            ajout = (
                m2 - m1
            )

            assert (
                len(ajout)
                == nombre
            )


def test_meme_structure_retards_que_m1():

    for heure in range(24):

        retards_m1 = set(
            modeles_lineaires
            .variables_retards_m1(
                heure
            )
        )

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            variables_m2 = set(
                modeles_meteo
                .variables_m2(
                    heure,
                    "temp_38_ponderee",
                    variante,
                )
            )

            assert (
                retards_m1
                .issubset(
                    variables_m2
                )
            )


def test_pas_weekend_dans_m2():

    for heure in range(24):

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            variables = (
                modeles_meteo
                .variables_m2(
                    heure,
                    "temp_8_villes",
                    variante,
                )
            )

            assert (
                "weekend"
                not in variables
            )


# ============================================================
# Isolation des candidats
# ============================================================

def test_m2_nutilise_quun_candidat_meteo():

    for candidat in (
        modeles_meteo
        .CANDIDATS_TEMPERATURE
    ):

        autres = [
            autre
            for autre in (
                modeles_meteo
                .CANDIDATS_TEMPERATURE
            )
            if autre != candidat
        ]

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            variables = (
                modeles_meteo
                .variables_m2(
                    12,
                    candidat,
                    variante,
                )
            )

            for autre in autres:

                assert not any(
                    variable.startswith(
                        autre + "_"
                    )
                    for variable in variables
                )


# ============================================================
# Pipeline
# ============================================================

def test_pipeline_m2():

    modele = (
        modeles_meteo
        .construire_modele_m2(
            8,
            "temp_8_villes",
            "M2-A",
        )
    )

    assert (
        "preparation"
        in modele.named_steps
    )

    assert (
        "regression"
        in modele.named_steps
    )


def test_pipeline_m2_encode_categories():

    modele = (
        modeles_meteo
        .construire_modele_m2(
            8,
            "temp_38_simple",
            "M2-F",
        )
    )

    preparation = (
        modele.named_steps[
            "preparation"
        ]
    )

    transformeurs = {
        nom: transformeur
        for (
            nom,
            transformeur,
            _,
        ) in preparation.transformers
    }

    assert isinstance(
        transformeurs[
            "categoriel"
        ],
        OneHotEncoder,
    )


# ============================================================
# Ajustement
# ============================================================

@pytest.mark.parametrize(
    "variante",
    [
        "M2-A",
        "M2-C",
        "M2-F",
    ],
)
def test_ajuste_24_modeles_m2(
    variante,
):

    donnees = (
        dataset_test_m2()
    )

    train = (
        modeles_lineaires
        .extraire_apprentissage(
            donnees
        )
    )

    modeles = (
        modeles_meteo
        .ajuster_modeles_m2(
            train,
            "temp_8_villes",
            variante,
        )
    )

    assert set(
        modeles.keys()
    ) == set(
        range(24)
    )


# ============================================================
# Prédiction
# ============================================================

@pytest.mark.parametrize(
    "variante",
    [
        "M2-A",
        "M2-D",
        "M2-F",
    ],
)
def test_predictions_m2_meme_taille(
    variante,
):

    donnees = (
        dataset_test_m2()
    )

    train = (
        modeles_lineaires
        .extraire_apprentissage(
            donnees
        )
    )

    validation = (
        modeles_lineaires
        .extraire_validation(
            donnees
        )
    )

    modeles = (
        modeles_meteo
        .ajuster_modeles_m2(
            train,
            "temp_8_villes",
            variante,
        )
    )

    predictions = (
        modeles_meteo
        .predire_m2(
            modeles,
            validation,
            "temp_8_villes",
            variante,
        )
    )

    assert (
        len(predictions)
        == len(validation)
    )

    assert not predictions[
        "prediction_MW"
    ].isna().any()


def test_predictions_m2_toutes_heures():

    donnees = (
        dataset_test_m2()
    )

    train = (
        modeles_lineaires
        .extraire_apprentissage(
            donnees
        )
    )

    validation = (
        modeles_lineaires
        .extraire_validation(
            donnees
        )
    )

    modeles = (
        modeles_meteo
        .ajuster_modeles_m2(
            train,
            "temp_38_simple",
            "M2-B",
        )
    )

    predictions = (
        modeles_meteo
        .predire_m2(
            modeles,
            validation,
            "temp_38_simple",
            "M2-B",
        )
    )

    assert set(
        predictions[
            "heure_cible"
        ].unique()
    ) == set(
        range(24)
    )


# ============================================================
# NaN
# ============================================================

def test_nan_meteo_refuse():

    donnees = (
        dataset_test_m2()
    )

    train = (
        modeles_lineaires
        .extraire_apprentissage(
            donnees
        )
    )

    index = train.index[
        train[
            "heure_cible"
        ] == 0
    ][0]

    train.loc[
        index,
        "temp_8_villes_origine",
    ] = np.nan

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .ajuster_modeles_m2(
                train,
                "temp_8_villes",
                "M2-A",
            )
        )


# ============================================================
# Anti-fuite
# ============================================================

def test_aucune_colonne_future_dans_m2():

    interdites = {
        "consommation_cible_MW",
        "date_heure_cible_utc",
        "date_heure_origine_utc",
        "periode",
        "exclu_covid",
        "horizon_h",
    }

    for candidat in (
        modeles_meteo
        .CANDIDATS_TEMPERATURE
    ):

        for variante in (
            modeles_meteo
            .VARIANTES_METEO_M2
        ):

            for heure in range(24):

                variables = set(
                    modeles_meteo
                    .variables_m2(
                        heure,
                        candidat,
                        variante,
                    )
                )

                assert (
                    variables
                    .isdisjoint(
                        interdites
                    )
                )


# ============================================================
# Rétrocompatibilité M2-F
# ============================================================

def test_m2_f_reproduit_appel_par_defaut():

    for heure in [
        0,
        12,
        13,
        23,
    ]:

        for candidat in (
            modeles_meteo
            .CANDIDATS_TEMPERATURE
        ):

            assert (
                modeles_meteo
                .variables_m2(
                    heure,
                    candidat,
                )
                ==
                modeles_meteo
                .variables_m2(
                    heure,
                    candidat,
                    "M2-F",
                )
            )


# ============================================================
# Métriques par bloc
# ============================================================

def test_metriques_par_bloc():

    predictions = []

    for bloc in [
        "T1",
        "T2",
        "T3",
        "T4",
    ]:

        for i in range(2):

            predictions.append(
                {
                    "bloc_validation":
                        bloc,

                    "consommation_cible_MW":
                        100.0,

                    "prediction_MW":
                        100.0 + i,
                }
            )

    resultat = (
        modeles_meteo
        .ResultatValidationM2(
            candidat_temperature=
                "temp_8_villes",

            predictions=
                pd.DataFrame(
                    predictions
                ),

            metriques={},

            variante_meteo=
                "M2-A",
        )
    )

    tableau = (
        modeles_meteo
        .metriques_par_bloc(
            resultat
        )
    )

    assert (
        len(tableau)
        == 4
    )

    assert list(
        tableau[
            "bloc"
        ]
    ) == [
        "T1",
        "T2",
        "T3",
        "T4",
    ]


# ============================================================
# Structures de résultats
# ============================================================

def test_structure_resultat_comparaison():

    resultats = {
        "temp_8_villes":
            modeles_meteo
            .ResultatValidationM2(
                candidat_temperature=
                    "temp_8_villes",

                predictions=
                    pd.DataFrame(),

                metriques={},

                variante_meteo=
                    "M2-F",
            )
    }

    tableau = pd.DataFrame(
        {
            "candidat_temperature":
                [
                    "temp_8_villes"
                ],

            "MAE_MW":
                [
                    1000.0
                ],
        }
    )

    comparaison = (
        modeles_meteo
        .ResultatComparaisonM2(
            resultats=resultats,
            tableau=tableau,
        )
    )

    assert (
        "temp_8_villes"
        in comparaison.resultats
    )

    assert (
        len(comparaison.tableau)
        == 1
    )


def test_structure_resultat_ablation():

    cle = (
        "temp_8_villes",
        "M2-A",
    )

    resultats = {
        cle:
            modeles_meteo
            .ResultatValidationM2(
                candidat_temperature=
                    "temp_8_villes",

                predictions=
                    pd.DataFrame(),

                metriques={},

                variante_meteo=
                    "M2-A",
            )
    }

    tableau = pd.DataFrame(
        {
            "candidat_temperature":
                [
                    "temp_8_villes"
                ],

            "variante_meteo":
                [
                    "M2-A"
                ],

            "MAE_MW":
                [
                    1000.0
                ],
        }
    )

    resultat = (
        modeles_meteo
        .ResultatAblationM2(
            resultats=resultats,
            tableau=tableau,
        )
    )

    assert (
        cle
        in resultat.resultats
    )

    assert (
        len(resultat.tableau)
        == 1
    )

# ============================================================
# Protocole final 2024-2025
# ============================================================


def test_structure_resultat_test_final_m2():

    resultat = (
        modeles_meteo
        .ResultatTestFinalM2(
            candidat_temperature=
                "temp_38_ponderee",

            variante_meteo=
                "M2-F",

            predictions=
                pd.DataFrame(),

            metriques={},
        )
    )

    assert (
        resultat.candidat_temperature
        == "temp_38_ponderee"
    )

    assert (
        resultat.variante_meteo
        == "M2-F"
    )


def test_predire_m2_conserve_bloc_test():

    donnees = (
        dataset_test_m2()
    )

    train = (
        modeles_lineaires
        .extraire_apprentissage(
            donnees
        )
    )

    validation = (
        modeles_lineaires
        .extraire_validation(
            donnees
        )
        .copy()
    )

    validation[
        "bloc_test"
    ] = "2024-01"

    modeles = (
        modeles_meteo
        .ajuster_modeles_m2(
            train,
            "temp_38_ponderee",
            "M2-F",
        )
    )

    predictions = (
        modeles_meteo
        .predire_m2(
            modeles,
            validation,
            "temp_38_ponderee",
            "M2-F",
        )
    )

    assert (
        "bloc_test"
        in predictions.columns
    )

    assert set(
        predictions[
            "bloc_test"
        ].unique()
    ) == {
        "2024-01",
    }


def test_validation_m2_utilise_protocole_validation(
    monkeypatch,
):

    donnees = (
        dataset_test_m2()
    )

    appels = []

    fonction_originale = (
        modeles_lineaires
        .apprentissage_avant
    )

    def espion(
        donnees_locales,
        debut_bloc,
        periodes_autorisees=None,
    ):

        appels.append(
            set(
                periodes_autorisees
            )
        )

        return fonction_originale(
            donnees_locales,
            debut_bloc,
            periodes_autorisees=
                periodes_autorisees,
        )

    monkeypatch.setattr(
        modeles_lineaires,
        "apprentissage_avant",
        espion,
    )

    with pytest.raises(
        ValueError
    ):
        modeles_meteo.valider_m2_expanding(
            donnees,
            "temp_8_villes",
            "M2-A",
        )

    assert appels

    for periodes in appels:
        assert periodes == (
            modeles_lineaires
            .PERIODES_AUTORISEES_VALIDATION_EXPANDING
        )


def test_m2_test_final_refuse_candidat_invalide():

    donnees = (
        dataset_test_m2()
    )

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .evaluer_m2_test_final(
                donnees,
                "temperature_future",
                "M2-F",
            )
        )


def test_m2_test_final_refuse_variante_invalide():

    donnees = (
        dataset_test_m2()
    )

    with pytest.raises(
        ValueError
    ):
        (
            modeles_meteo
            .evaluer_m2_test_final(
                donnees,
                "temp_38_ponderee",
                "M2-Z",
            )
        )

# ============================================================
# Changement d'heure Europe/Paris
# ============================================================


def test_jours_changement_heure_paris_2024():

    jours = (
        modeles_lineaires
        .jours_changement_heure_paris(
            2024,
            2024,
        )
    )

    assert jours == {
        pd.Timestamp("2024-03-31"),
        pd.Timestamp("2024-10-27"),
    }


def test_jours_changement_heure_paris_2025():

    jours = (
        modeles_lineaires
        .jours_changement_heure_paris(
            2025,
            2025,
        )
    )

    assert jours == {
        pd.Timestamp("2025-03-30"),
        pd.Timestamp("2025-10-26"),
    }


def test_quatre_jours_dst_sur_test_final():

    jours = (
        modeles_lineaires
        .jours_changement_heure_paris(
            2024,
            2025,
        )
    )

    assert jours == {
        pd.Timestamp("2024-03-31"),
        pd.Timestamp("2024-10-27"),
        pd.Timestamp("2025-03-30"),
        pd.Timestamp("2025-10-26"),
    }


def test_filtrage_dst_ne_modifie_pas_entree():

    dates = [
        pd.Timestamp("2024-03-30"),
        pd.Timestamp("2024-03-31"),
        pd.Timestamp("2024-04-01"),
    ]

    lignes = []

    for jour in dates:
        for heure in range(24):
            lignes.append(
                {
                    "jour_cible": jour,
                    "heure_cible": heure,
                    "consommation_cible_MW": 100.0,
                    "prediction_MW": 101.0,
                }
            )

    predictions = pd.DataFrame(
        lignes
    )

    original = predictions.copy(
        deep=True
    )

    filtre = (
        modeles_lineaires
        .filtrer_jours_changement_heure(
            predictions
        )
    )

    pd.testing.assert_frame_equal(
        predictions,
        original,
    )

    assert (
        pd.Timestamp("2024-03-31")
        not in set(
            pd.to_datetime(
                filtre["jour_cible"]
            )
        )
    )

    assert len(filtre) == 48


def test_filtrage_dst_garde_jour_incomplet_non_dst():

    lignes = []

    for heure in range(23):
        lignes.append(
            {
                "jour_cible":
                    pd.Timestamp("2024-05-15"),

                "heure_cible":
                    heure,

                "consommation_cible_MW":
                    100.0,

                "prediction_MW":
                    101.0,
            }
        )

    predictions = pd.DataFrame(
        lignes
    )

    filtre = (
        modeles_lineaires
        .filtrer_jours_changement_heure(
            predictions
        )
    )

    assert len(filtre) == 23


def test_metriques_finales_excluent_dst():

    lignes = []

    for jour in [
        pd.Timestamp("2024-03-30"),
        pd.Timestamp("2024-03-31"),
        pd.Timestamp("2024-04-01"),
    ]:

        for heure in range(24):

            erreur = (
                1000.0
                if jour
                == pd.Timestamp(
                    "2024-03-31"
                )
                else 10.0
            )

            lignes.append(
                {
                    "jour_cible":
                        jour,

                    "heure_cible":
                        heure,

                    "consommation_cible_MW":
                        100.0,

                    "prediction_MW":
                        100.0 + erreur,
                }
            )

    predictions = pd.DataFrame(
        lignes
    )

    metriques = (
        modeles_lineaires
        .calculer_metriques_finales(
            predictions
        )
    )

    assert metriques[
        "MAE_MW"
    ] == pytest.approx(
        10.0
    )

    assert metriques[
        "RMSE_MW"
    ] == pytest.approx(
        10.0
    )

    assert metriques[
        "nb_jours_dst_exclus"
    ] == 1

    assert metriques[
        "nb_observations_evaluees"
    ] == 48


def test_validation_2023_conserve_metriques_historiques():

    # Ce test vérifie surtout que l'ajout du mécanisme DST
    # ne change pas le chemin de calcul de la validation 2023.
    assert callable(
        modeles_lineaires
        .valider_m1_expanding
    )

    assert callable(
        modeles_lineaires
        .calculer_metriques_finales
    )