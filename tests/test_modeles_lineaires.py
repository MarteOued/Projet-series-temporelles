import numpy as np

import pandas as pd

import pytest

from src import modeles_lineaires

# ============================================================

# Dataset synthétique

# ============================================================

def dataset_test():

    """Construit un petit dataset synthétique pour tester M1."""

    lignes = []

    dates_train = pd.date_range(

        "2022-01-01",

        periods=10,

        freq="D",

    )

    dates_validation = pd.date_range(

        "2023-01-01",

        periods=3,

        freq="D",

    )

    for periode, dates in [

        ("apprentissage", dates_train),

        ("validation", dates_validation),

    ]:

        for jour in dates:

            for heure in range(24):

                base = (

                    40_000

                    + 100 * heure

                    + 20 * jour.day

                )

                lignes.append(

                    {

                        "jour_cible": jour,

                        "heure_cible": heure,

                        "periode": periode,

                        "exclu_covid": False,

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

                        "weekend":

                            int(

                                jour.dayofweek >= 5

                            ),

                        "ferie": 0,

                        "veille_ferie": 0,

                        "lendemain_ferie": 0,

                        "pont_potentiel": 0,

                        "vacances_A": 0,

                        "vacances_B": 0,

                        "vacances_C": 0,

                        "consommation_cible_MW":

                            base,

                    }

                )

    return pd.DataFrame(lignes)

# ============================================================

# Retards M1

# ============================================================

def test_retards_heures_0_a_12():

    for heure in range(13):

        variables = (

            modeles_lineaires

            .variables_retards_m1(

                heure

            )

        )

        assert variables == [

            "conso_veille_effective_MW",

            "conso_lag48_MW",

            "conso_lag168_MW",

        ]

def test_retards_heures_13_a_23():

    for heure in range(13, 24):

        variables = (

            modeles_lineaires

            .variables_retards_m1(

                heure

            )

        )

        assert variables == [

            "conso_lag48_MW",

            "conso_lag168_MW",

        ]

def test_pas_duplication_lag48_apres_12h():

    for heure in range(13, 24):

        variables = (

            modeles_lineaires

            .variables_retards_m1(

                heure

            )

        )

        assert (

            "conso_veille_effective_MW"

            not in variables

        )

        assert variables.count(

            "conso_lag48_MW"

        ) == 1

def test_lag24_effectif_present_avant_13h():

    for heure in range(13):

        variables = (

            modeles_lineaires

            .variables_retards_m1(

                heure

            )

        )

        assert (

            "conso_veille_effective_MW"

            in variables

        )

# ============================================================

# Validation des heures

# ============================================================

def test_heure_invalide_negative():

    with pytest.raises(ValueError):

        modeles_lineaires.variables_m1(

            -1

        )

def test_heure_invalide_superieure_23():

    with pytest.raises(ValueError):

        modeles_lineaires.variables_m1(

            24

        )

def test_heure_non_entiere():

    with pytest.raises(TypeError):

        modeles_lineaires.variables_m1(

            12.5

        )

# ============================================================

# Variables calendaires

# ============================================================

def test_calendrier_retenu():

    variables = (

        modeles_lineaires

        .VARIABLES_CATEGORIELLES_M1

        + modeles_lineaires

        .VARIABLES_CALENDRIER_BINAIRES_M1

    )

    assert "jour_semaine" in variables

    assert "mois" in variables

    assert "weekend" not in variables

    assert "vacances_A" in variables

    assert "vacances_B" in variables

    assert "vacances_C" in variables

    assert "nb_zones_vacances" not in variables

    assert "periode_noel" not in variables

def test_aucune_metadata_dans_m1():

    interdites = {

        "jour_origine",

        "date_heure_origine_utc",

        "jour_cible",

        "date_heure_cible_utc",

        "heure_cible",

        "horizon_h",

        "periode",

        "exclu_covid",

        "consommation_cible_MW",

        "retard_effectif_h",

    }

    for heure in range(24):

        variables = set(

            modeles_lineaires

            .variables_m1(

                heure

            )

        )

        assert variables.isdisjoint(

            interdites

        )

def test_aucune_meteo_dans_m1():

    for heure in range(24):

        variables = (

            modeles_lineaires

            .variables_m1(

                heure

            )

        )

        assert not any(

            variable.startswith("temp_")

            for variable in variables

        )

# ============================================================

# Extraction apprentissage / validation

# ============================================================

def test_extraire_apprentissage_exclut_covid():

    donnees = dataset_test()

    index = donnees.index[

        donnees["periode"]

        == "apprentissage"

    ][0]

    donnees.loc[

        index,

        "exclu_covid",

    ] = True

    train = (

        modeles_lineaires

        .extraire_apprentissage(

            donnees

        )

    )

    assert (

        train["periode"]

        == "apprentissage"

    ).all()

    assert not train[

        "exclu_covid"

    ].any()

    assert len(train) == 239

def test_extraire_validation():

    donnees = dataset_test()

    validation = (

        modeles_lineaires

        .extraire_validation(

            donnees

        )

    )

    assert (

        validation["periode"]

        == "validation"

    ).all()

    assert len(validation) == 72

# ============================================================

# Ajustement / prédiction

# ============================================================

def test_ajuste_24_modeles():

    donnees = dataset_test()

    train = (

        modeles_lineaires

        .extraire_apprentissage(

            donnees

        )

    )

    modeles = (

        modeles_lineaires

        .ajuster_modeles_m1(

            train

        )

    )

    assert set(

        modeles.keys()

    ) == set(range(24))

def test_predictions_meme_nombre_lignes():

    donnees = dataset_test()

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

        modeles_lineaires

        .ajuster_modeles_m1(

            train

        )

    )

    predictions = (

        modeles_lineaires

        .predire_m1(

            modeles,

            validation,

        )

    )

    assert len(predictions) == len(

        validation

    )

    assert not predictions[

        "prediction_MW"

    ].isna().any()

def test_predictions_toutes_heures():

    donnees = dataset_test()

    resultat = (

        modeles_lineaires

        .evaluer_m1(

            donnees

        )

    )

    assert set(

        resultat.predictions[

            "heure_cible"

        ].unique()

    ) == set(range(24))

# ============================================================

# Métriques horaires

# ============================================================

def test_metriques_parfaites():

    predictions = pd.DataFrame(

        {

            "consommation_cible_MW": [

                100.0,

                200.0,

                300.0,

            ],

            "prediction_MW": [

                100.0,

                200.0,

                300.0,

            ],

        }

    )

    metriques = (

        modeles_lineaires

        .calculer_metriques(

            predictions

        )

    )

    assert (

        metriques["MAE_MW"]

        == pytest.approx(0.0)

    )

    assert (

        metriques["RMSE_MW"]

        == pytest.approx(0.0)

    )

def test_metriques_connues():

    predictions = pd.DataFrame(

        {

            "consommation_cible_MW": [

                100.0,

                200.0,

            ],

            "prediction_MW": [

                110.0,

                180.0,

            ],

        }

    )

    metriques = (

        modeles_lineaires

        .calculer_metriques(

            predictions

        )

    )

    assert (

        metriques["MAE_MW"]

        == pytest.approx(15.0)

    )

    assert (

        metriques["RMSE_MW"]

        == pytest.approx(

            np.sqrt(250.0)

        )

    )

# ============================================================

# Métriques journalières

# ============================================================

def test_metriques_journalieres_parfaites():

    lignes = []

    for heure in range(24):

        valeur = 1000.0 + heure

        lignes.append(

            {

                "jour_cible":

                    pd.Timestamp(

                        "2023-01-01"

                    ),

                "heure_cible":

                    heure,

                "consommation_cible_MW":

                    valeur,

                "prediction_MW":

                    valeur,

            }

        )

    predictions = pd.DataFrame(

        lignes

    )

    metriques = (

        modeles_lineaires

        .calculer_metriques_journalieres(

            predictions

        )

    )

    assert (

        metriques[

            "MAE_total_journalier_MWh"

        ]

        == pytest.approx(0.0)

    )

    assert (

        metriques["MAE_pointe_MW"]

        == pytest.approx(0.0)

    )

    assert (

        metriques["MAE_heure_pointe_h"]

        == pytest.approx(0.0)

    )

    assert (

        metriques["nb_jours_complets"]

        == 1

    )

def test_jour_incomplet_exclu_metriques_journalieres():

    lignes = []

    for heure in range(24):

        lignes.append(

            {

                "jour_cible":

                    pd.Timestamp(

                        "2023-01-01"

                    ),

                "heure_cible":

                    heure,

                "consommation_cible_MW":

                    1000.0 + heure,

                "prediction_MW":

                    1000.0 + heure,

            }

        )

    for heure in range(23):

        lignes.append(

            {

                "jour_cible":

                    pd.Timestamp(

                        "2023-01-02"

                    ),

                "heure_cible":

                    heure,

                "consommation_cible_MW":

                    2000.0 + heure,

                "prediction_MW":

                    5000.0,

            }

        )

    predictions = pd.DataFrame(

        lignes

    )

    metriques = (

        modeles_lineaires

        .calculer_metriques_journalieres(

            predictions

        )

    )

    assert (

        metriques["nb_jours_complets"]

        == 1

    )

    assert (

        metriques[

            "MAE_total_journalier_MWh"

        ]

        == pytest.approx(0.0)

    )

# ============================================================

# Anti-fuite validation fixe

# ============================================================

def test_validation_ne_modifie_pas_train():

    donnees = dataset_test()

    train_original = (

        modeles_lineaires

        .extraire_apprentissage(

            donnees

        )

    )

    modifiees = donnees.copy()

    masque = (

        modifiees["periode"]

        == "validation"

    )

    modifiees.loc[

        masque,

        "consommation_cible_MW",

    ] = 999_999.0

    train_modifie = (

        modeles_lineaires

        .extraire_apprentissage(

            modifiees

        )

    )

    pd.testing.assert_frame_equal(

        train_original,

        train_modifie,

    )

# ============================================================

# Encodage catégoriel

# ============================================================

def test_weekend_non_duplique_avec_jour_semaine():

    for heure in range(24):

        variables = (

            modeles_lineaires

            .variables_m1(

                heure

            )

        )

        assert "jour_semaine" in variables

        assert "weekend" not in variables

def test_jour_semaine_et_mois_categoriels():

    assert (

        modeles_lineaires

        .VARIABLES_CATEGORIELLES_M1

        == [

            "jour_semaine",

            "mois",

        ]

    )

def test_pipeline_contient_one_hot_encoder():

    modele = (

        modeles_lineaires

        .construire_modele_m1(

            8

        )

    )

    preparation = (

        modele.named_steps[

            "preparation"

        ]

    )

    transformeurs = {

        nom: transformeur

        for nom, transformeur, _ in preparation.transformers

    }

    encodeur = transformeurs[

        "categoriel"

    ]

    from sklearn.preprocessing import OneHotEncoder

    assert isinstance(

        encodeur,

        OneHotEncoder,

    )

# ============================================================

# Blocs de validation chronologique

# ============================================================

def test_blocs_validation_2023():

    blocs = (

        modeles_lineaires

        .BLOCS_VALIDATION_2023

    )

    assert len(blocs) == 4

    assert blocs[0][0] == "T1"

    assert (

        blocs[0][1]

        == pd.Timestamp(

            "2023-01-01"

        )

    )

    assert blocs[-1][0] == "T4"

    assert (

        blocs[-1][2]

        == pd.Timestamp(

            "2024-01-01"

        )

    )

# ============================================================

# Apprentissage expanding

# ============================================================

def test_apprentissage_avant_exclut_bloc_courant():

    donnees = dataset_test()

    train = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-01",

        )

    )

    jours = pd.to_datetime(

        train["jour_cible"]

    )

    assert (

        jours

        < pd.Timestamp(

            "2023-01-01"

        )

    ).all()

def test_apprentissage_expanding_integre_passe_validation():

    donnees = dataset_test()

    train_tardif = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

    )

    jours = pd.to_datetime(

        train_tardif["jour_cible"]

    )

    jours_uniques = set(

        jours

    )

    assert (

        pd.Timestamp(

            "2023-01-01"

        )

        in jours_uniques

    )

    assert (

        pd.Timestamp(

            "2023-01-02"

        )

        in jours_uniques

    )

    assert (

        pd.Timestamp(

            "2023-01-03"

        )

        not in jours_uniques

    )

def test_apprentissage_expanding_exclut_covid():

    donnees = dataset_test()

    masque = (

        pd.to_datetime(

            donnees["jour_cible"]

        )

        == pd.Timestamp(

            "2023-01-01"

        )

    )

    donnees.loc[

        masque,

        "exclu_covid",

    ] = True

    train = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

    )

    jours = set(

        pd.to_datetime(

            train["jour_cible"]

        )

    )

    assert (

        pd.Timestamp(

            "2023-01-01"

        )

        not in jours

    )

# ============================================================

# Sécurisation des périodes expanding

# ============================================================

def test_apprentissage_expanding_exclut_periode_test():

    """

    Une ligne de période test ne doit jamais entrer dans

    l'apprentissage, même si sa date est antérieure au bloc.

    """

    donnees = dataset_test()

    ligne_test = donnees.iloc[[0]].copy()

    ligne_test["jour_cible"] = pd.Timestamp(

        "2022-12-20"

    )

    ligne_test["periode"] = "test"

    ligne_test["consommation_cible_MW"] = (

        999_999.0

    )

    donnees = pd.concat(

        [

            donnees,

            ligne_test,

        ],

        ignore_index=True,

    )

    train = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

    )

    assert not (

        train["periode"] == "test"

    ).any()

    assert not (

        train["consommation_cible_MW"]

        == 999_999.0

    ).any()

def test_apprentissage_expanding_exclut_periodes_non_autorisees():

    """

    Les périodes bonus ou inconnues sont exclues de l'expanding.

    """

    donnees = dataset_test()

    exemples = []

    for periode, valeur in [

        ("bonus", 888_888.0),

        ("inconnue", 777_777.0),

    ]:

        ligne = donnees.iloc[[0]].copy()

        ligne["jour_cible"] = pd.Timestamp(

            "2022-12-20"

        )

        ligne["periode"] = periode

        ligne["consommation_cible_MW"] = valeur

        exemples.append(

            ligne

        )

    donnees = pd.concat(

        [

            donnees,

            *exemples,

        ],

        ignore_index=True,

    )

    train = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

    )

    assert set(

        train["periode"].unique()

    ).issubset(

        {

            "apprentissage",

            "validation",

        }

    )

    assert not train[

        "consommation_cible_MW"

    ].isin(

        [

            888_888.0,

            777_777.0,

        ]

    ).any()

def test_apprentissage_expanding_exclut_avant_2016():

    """

    Même correctement étiquetée, une observation antérieure

    au début officiel de l'apprentissage ne doit pas être utilisée.

    """

    donnees = dataset_test()

    ancienne = donnees.iloc[[0]].copy()

    ancienne["jour_cible"] = pd.Timestamp(

        "2015-12-31"

    )

    ancienne["periode"] = "apprentissage"

    ancienne["consommation_cible_MW"] = (

        666_666.0

    )

    donnees = pd.concat(

        [

            donnees,

            ancienne,

        ],

        ignore_index=True,

    )

    train = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

    )

    jours = pd.to_datetime(

        train["jour_cible"]

    )

    assert (

        jours

        >= pd.Timestamp(

            "2016-01-01"

        )

    ).all()

    assert not (

        train["consommation_cible_MW"]

        == 666_666.0

    ).any()

def test_periodes_autorisees_expanding():

    assert (

        modeles_lineaires

        .PERIODES_AUTORISEES_EXPANDING

        == {

            "apprentissage",

            "validation",

        }

    )

def test_date_debut_apprentissage_expanding():

    assert (

        modeles_lineaires

        .DATE_DEBUT_APPRENTISSAGE

        == pd.Timestamp(

            "2016-01-01"

        )

    )

# ============================================================

# Anti-fuite expanding

# ============================================================

def test_validation_expanding_anti_fuite():

    """

    Modifier les cibles futures ne doit pas modifier

    l'apprentissage disponible avant ces cibles.

    """

    donnees = dataset_test()

    avant = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-02",

        )

        .reset_index(

            drop=True

        )

    )

    modifiees = donnees.copy()

    jours = pd.to_datetime(

        modifiees["jour_cible"]

    )

    modifiees.loc[

        jours

        >= pd.Timestamp(

            "2023-01-02"

        ),

        "consommation_cible_MW",

    ] = 999_999.0

    apres = (

        modeles_lineaires

        .apprentissage_avant(

            modifiees,

            "2023-01-02",

        )

        .reset_index(

            drop=True

        )

    )

    pd.testing.assert_frame_equal(

        avant,

        apres,

    )

def test_periode_test_passee_ne_modifie_pas_apprentissage():

    """

    Même datée avant le bloc courant, une observation appartenant

    au test ne doit avoir aucun effet sur l'apprentissage.

    """

    donnees = dataset_test()

    reference = (

        modeles_lineaires

        .apprentissage_avant(

            donnees,

            "2023-01-03",

        )

        .reset_index(

            drop=True

        )

    )

    fuite = donnees.iloc[[0]].copy()

    fuite["jour_cible"] = pd.Timestamp(

        "2022-12-31"

    )

    fuite["periode"] = "test"

    fuite["consommation_cible_MW"] = (

    9_999_999

)

    modifiees = pd.concat(

        [

            donnees,

            fuite,

        ],

        ignore_index=True,

    )

    securise = (

        modeles_lineaires

        .apprentissage_avant(

            modifiees,

            "2023-01-03",

        )

        .reset_index(

            drop=True

        )

    )

    pd.testing.assert_frame_equal(

        reference,

        securise,

    )

# ============================================================
# Protocole final 2024-2025
# ============================================================

def test_periodes_autorisees_test_final():
    assert modeles_lineaires.PERIODES_AUTORISEES_TEST_FINAL == {
        "apprentissage",
        "validation",
        "test",
    }

def test_blocs_test_final_2024_2025():
    blocs = modeles_lineaires.BLOCS_TEST_FINAL_2024_2025

    assert len(blocs) == 24
    assert blocs[0] == (
        "2024-01",
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-02-01"),
    )
    assert blocs[-1] == (
        "2025-12",
        pd.Timestamp("2025-12-01"),
        pd.Timestamp("2026-01-01"),
    )

def test_test_passe_autorise_pour_test_final():
    donnees = dataset_test()

    ligne_passee = donnees.iloc[[0]].copy()
    ligne_passee["jour_cible"] = pd.Timestamp("2024-01-15")
    ligne_passee["periode"] = "test"
    ligne_passee["consommation_cible_MW"] = 555_555

    donnees = pd.concat(
        [donnees, ligne_passee],
        ignore_index=True,
    )

    train = modeles_lineaires.apprentissage_avant(
        donnees,
        "2024-02-01",
        periodes_autorisees=(
            modeles_lineaires.PERIODES_AUTORISEES_TEST_FINAL
        ),
    )

    assert 555_555 in set(train["consommation_cible_MW"])

def test_mois_courant_et_futur_exclus_du_test_final():
    donnees = dataset_test()

    lignes = []
    for date, valeur in [
        ("2024-01-31", 111_111),
        ("2024-02-01", 222_222),
        ("2024-03-01", 333_333),
    ]:
        ligne = donnees.iloc[[0]].copy()
        ligne["jour_cible"] = pd.Timestamp(date)
        ligne["periode"] = "test"
        ligne["consommation_cible_MW"] = valeur
        lignes.append(ligne)

    donnees = pd.concat(
        [donnees, *lignes],
        ignore_index=True,
    )

    train = modeles_lineaires.apprentissage_avant(
        donnees,
        "2024-02-01",
        periodes_autorisees=(
            modeles_lineaires.PERIODES_AUTORISEES_TEST_FINAL
        ),
    )

    valeurs = set(train["consommation_cible_MW"])
    assert 111_111 in valeurs
    assert 222_222 not in valeurs
    assert 333_333 not in valeurs

def test_validation_2023_reste_stricte_par_defaut():
    donnees = dataset_test()

    ligne_test = donnees.iloc[[0]].copy()
    ligne_test["jour_cible"] = pd.Timestamp("2022-12-31")
    ligne_test["periode"] = "test"
    ligne_test["consommation_cible_MW"] = 444_444

    donnees = pd.concat(
        [donnees, ligne_test],
        ignore_index=True,
    )

    train = modeles_lineaires.apprentissage_avant(
        donnees,
        "2023-01-03",
    )

    assert 444_444 not in set(train["consommation_cible_MW"])

def test_periode_autorisee_inconnue_refusee():
    donnees = dataset_test()

    with pytest.raises(ValueError):
        modeles_lineaires.apprentissage_avant(
            donnees,
            "2023-01-03",
            periodes_autorisees={"apprentissage", "inconnue"},
        )


def test_compteur_dst_quand_le_dataset_les_a_deja_retires():
    # Le dataset ne contient déjà plus les jours de changement d'heure :
    # le compteur doit quand même dire combien de jours ne sont pas notés.
    jours = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    jours = jours[~jours.isin(modeles_lineaires.jours_changement_heure_paris(2024, 2024))]
    predictions = pd.DataFrame({
        "jour_cible": jours.repeat(24),
        "heure_cible": list(range(24)) * len(jours),
        "consommation_cible_MW": 50_000.0,
        "prediction_MW": 50_010.0,
    })
    metriques = modeles_lineaires.calculer_metriques_finales(predictions)
    assert metriques["nb_jours_dst_exclus"] == 2
    assert metriques["nb_jours_complets"] == 364
