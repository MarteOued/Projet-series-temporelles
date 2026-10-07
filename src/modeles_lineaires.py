"""
Modèle linéaire M1 pour la prévision de consommation électrique.

Principes
---------
- Un modèle indépendant par heure cible H.
- Validation strictement chronologique.
- Jour de semaine et mois traités comme variables catégorielles.
- Les cibles Covid sont exclues de l'apprentissage.
- Les données futures ne sont jamais utilisées pour ajuster un modèle.

Disponibilité des retards à 14 h Paris le jour J
-------------------------------------------------
Pour prévoir l'heure H de J+1 :

H <= 12 :
    lag24 + lag48 + lag168

H > 12 :
    lag48 + lag168

Validation 2023
---------------
La validation est réalisée en quatre blocs trimestriels à fenêtre
d'apprentissage croissante :

Q1 : apprentissage jusqu'au 31/12/2022
Q2 : apprentissage jusqu'au 31/03/2023
Q3 : apprentissage jusqu'au 30/06/2023
Q4 : apprentissage jusqu'au 30/09/2023

Les prédictions d'un trimestre sont donc toujours produites avec
des données dont le jour cible est strictement antérieur au bloc évalué.

Évaluation finale 2024-2025
---------------------------
- Ré-estimation expanding au début de chaque mois.
- Le test passé peut entrer dans l'apprentissage.
- Le mois courant et le futur sont interdits dans l'apprentissage.
- Les journées de changement d'heure Europe/Paris sont conservées
  dans les données et dans l'historique, mais exclues des métriques
  finales conformément au protocole.
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


# ============================================================
# Colonnes générales
# ============================================================

COLONNE_CIBLE = "consommation_cible_MW"
COLONNE_HEURE = "heure_cible"
COLONNE_PERIODE = "periode"
COLONNE_COVID = "exclu_covid"
COLONNE_JOUR = "jour_cible"


# ============================================================
# Périodes autorisées pour l'apprentissage expanding
# ============================================================

PERIODES_AUTORISEES_VALIDATION_EXPANDING = {
    "apprentissage",
    "validation",
}

# Alias conservé pour compatibilité avec le code existant.
PERIODES_AUTORISEES_EXPANDING = (
    PERIODES_AUTORISEES_VALIDATION_EXPANDING
)

PERIODES_AUTORISEES_TEST_FINAL = {
    "apprentissage",
    "validation",
    "test",
}

DATE_DEBUT_APPRENTISSAGE = pd.Timestamp("2016-01-01")


# ============================================================
# Variables M1
# ============================================================

VARIABLES_CATEGORIELLES_M1 = [
    "jour_semaine",
    "mois",
]

VARIABLES_CALENDRIER_BINAIRES_M1 = [
    "ferie",
    "veille_ferie",
    "lendemain_ferie",
    "pont_potentiel",
    "vacances_A",
    "vacances_B",
    "vacances_C",
]

# weekend n'est pas ajouté :
# avec jour_semaine encodé catégoriellement, il est entièrement
# déterminé par samedi/dimanche et serait donc redondant.
#
# nb_zones_vacances n'est pas ajouté car vacances_A/B/C sont retenues.
# periode_noel n'est pas retenue après l'ablation calendrier.


# ============================================================
# Structure des résultats
# ============================================================

@dataclass
class ResultatValidation:
    predictions: pd.DataFrame
    metriques: dict[str, float]


# ============================================================
# Vérifications
# ============================================================

def verifier_colonnes(
    donnees: pd.DataFrame,
    colonnes: list[str],
) -> None:
    """Vérifie que les colonnes demandées existent."""

    manquantes = [
        colonne
        for colonne in colonnes
        if colonne not in donnees.columns
    ]

    if manquantes:
        raise ValueError(
            "Colonnes manquantes : "
            + ", ".join(manquantes)
        )


def verifier_heure(
    heure: int,
) -> None:
    """Vérifie qu'une heure appartient à [0, 23]."""

    if not isinstance(
        heure,
        (int, np.integer),
    ):
        raise TypeError(
            "L'heure cible doit être un entier."
        )

    if not 0 <= heure <= 23:
        raise ValueError(
            f"Heure cible invalide : {heure}."
        )


# ============================================================
# Variables explicatives
# ============================================================

def variables_retards_m1(
    heure: int,
) -> list[str]:
    """
    Retourne les retards causalement disponibles pour H.
    """

    verifier_heure(heure)

    if heure <= 12:
        return [
            "conso_veille_effective_MW",
            "conso_lag48_MW",
            "conso_lag168_MW",
        ]

    return [
        "conso_lag48_MW",
        "conso_lag168_MW",
    ]


def variables_numeriques_m1(
    heure: int,
) -> list[str]:
    """
    Variables non catégorielles de M1.
    """

    return (
        variables_retards_m1(heure)
        + list(
            VARIABLES_CALENDRIER_BINAIRES_M1
        )
    )


def variables_m1(
    heure: int,
) -> list[str]:
    """
    Ensemble des variables M1 pour l'heure H.
    """

    return (
        variables_numeriques_m1(heure)
        + list(
            VARIABLES_CATEGORIELLES_M1
        )
    )


# ============================================================
# Pipeline de régression
# ============================================================

def construire_modele_m1(
    heure: int,
) -> Pipeline:
    """
    Construit le pipeline M1 pour une heure cible.

    jour_semaine :
        catégories fixes 0,...,6

    mois :
        catégories fixes 1,...,12

    drop="first" évite la redondance complète avec l'intercept.
    """

    verifier_heure(heure)

    numeriques = variables_numeriques_m1(
        heure
    )

    categorielle = ColumnTransformer(
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
                VARIABLES_CATEGORIELLES_M1,
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
                categorielle,
            ),
            (
                "regression",
                LinearRegression(),
            ),
        ]
    )


# ============================================================
# Gestion des périodes
# ============================================================

def _normaliser_jour(
    serie: pd.Series,
) -> pd.Series:
    """
    Convertit une colonne de dates en dates pandas normalisées.
    """

    return pd.to_datetime(
        serie
    ).dt.normalize()


def extraire_apprentissage(
    donnees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extrait l'apprentissage initial 2016-2022 hors cibles Covid.
    """

    verifier_colonnes(
        donnees,
        [
            COLONNE_PERIODE,
            COLONNE_COVID,
        ],
    )

    masque = (
        (
            donnees[
                COLONNE_PERIODE
            ]
            == "apprentissage"
        )
        & (
            ~donnees[
                COLONNE_COVID
            ].astype(bool)
        )
    )

    return donnees.loc[
        masque
    ].copy()


def extraire_validation(
    donnees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Extrait uniquement la validation 2023.
    """

    verifier_colonnes(
        donnees,
        [
            COLONNE_PERIODE,
        ],
    )

    return donnees.loc[
        donnees[
            COLONNE_PERIODE
        ] == "validation"
    ].copy()


def apprentissage_avant(
    donnees: pd.DataFrame,
    debut_bloc,
    periodes_autorisees=None,
) -> pd.DataFrame:
    """
    Construit l'apprentissage strictement disponible avant un bloc.
    """

    verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_PERIODE,
            COLONNE_COVID,
            COLONNE_CIBLE,
        ],
    )

    if periodes_autorisees is None:
        periodes_autorisees = (
            PERIODES_AUTORISEES_VALIDATION_EXPANDING
        )

    periodes_autorisees = set(
        periodes_autorisees
    )

    periodes_connues = {
        "apprentissage",
        "validation",
        "test",
    }

    if not periodes_autorisees:
        raise ValueError(
            "periodes_autorisees ne peut pas être vide."
        )

    inconnues = (
        periodes_autorisees
        - periodes_connues
    )

    if inconnues:
        raise ValueError(
            "Périodes d'apprentissage inconnues : "
            + ", ".join(
                sorted(inconnues)
            )
        )

    debut_bloc = pd.Timestamp(
        debut_bloc
    ).normalize()

    jours = _normaliser_jour(
        donnees[
            COLONNE_JOUR
        ]
    )

    masque = (
        donnees[
            COLONNE_PERIODE
        ].isin(
            periodes_autorisees
        )
        & (
            jours
            >= DATE_DEBUT_APPRENTISSAGE
        )
        & (
            jours
            < debut_bloc
        )
        & (
            ~donnees[
                COLONNE_COVID
            ].astype(bool)
        )
    )

    apprentissage = donnees.loc[
        masque
    ].copy()

    if apprentissage.empty:
        raise ValueError(
            "Aucune donnée autorisée disponible avant "
            f"{debut_bloc.date()}."
        )

    return apprentissage


# ============================================================
# Ajustement et prédiction
# ============================================================

def ajuster_modeles_m1(
    apprentissage: pd.DataFrame,
) -> dict[int, Pipeline]:
    """
    Ajuste un modèle indépendant pour chacune des 24 heures.
    """

    verifier_colonnes(
        apprentissage,
        [
            COLONNE_HEURE,
            COLONNE_CIBLE,
        ],
    )

    modeles: dict[int, Pipeline] = {}

    for heure in range(24):

        variables = variables_m1(
            heure
        )

        verifier_colonnes(
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
                "Aucune observation d'apprentissage "
                f"pour l'heure {heure}."
            )

        X = donnees_h[
            variables
        ]

        y = donnees_h[
            COLONNE_CIBLE
        ]

        if X.isna().any().any():
            raise ValueError(
                f"NaN dans X pour l'heure {heure}."
            )

        if y.isna().any():
            raise ValueError(
                f"NaN dans y pour l'heure {heure}."
            )

        modele = construire_modele_m1(
            heure
        )

        modele.fit(
            X,
            y,
        )

        modeles[
            heure
        ] = modele

    return modeles


def predire_m1(
    modeles: dict[int, Pipeline],
    donnees: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produit les prédictions des 24 modèles.
    """

    verifier_colonnes(
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
                f"Modèle absent pour l'heure {heure}."
            )

        variables = variables_m1(
            heure
        )

        verifier_colonnes(
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
                f"NaN dans X pour l'heure {heure}."
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
            "Aucune prédiction produite."
        )

    return (
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


# ============================================================
# Gestion des jours de changement d'heure
# ============================================================

def jours_changement_heure_paris(
    annee_debut: int,
    annee_fin: int,
) -> set[pd.Timestamp]:
    """
    Retourne les dates locales Europe/Paris où l'offset UTC change.

    La détection est calculée à partir du fuseau Europe/Paris :
    aucune date de changement d'heure n'est codée en dur.

    Les dates retournées sont des Timestamp naïfs normalisés,
    compatibles avec la colonne jour_cible.
    """

    if not isinstance(
        annee_debut,
        (int, np.integer),
    ):
        raise TypeError(
            "annee_debut doit être un entier."
        )

    if not isinstance(
        annee_fin,
        (int, np.integer),
    ):
        raise TypeError(
            "annee_fin doit être un entier."
        )

    if annee_fin < annee_debut:
        raise ValueError(
            "annee_fin doit être supérieure ou égale "
            "à annee_debut."
        )

    debut_utc = pd.Timestamp(
        f"{annee_debut}-01-01 00:00:00",
        tz="UTC",
    )

    fin_utc = pd.Timestamp(
        f"{annee_fin + 1}-01-01 00:00:00",
        tz="UTC",
    )

    heures_utc = pd.date_range(
        debut_utc,
        fin_utc,
        freq="h",
        inclusive="left",
    )

    heures_paris = (
        heures_utc.tz_convert(
            "Europe/Paris"
        )
    )

    offsets = pd.Series(
        [
            instant.utcoffset()
            for instant in heures_paris
        ],
        index=heures_paris,
    )

    changement = (
        offsets
        != offsets.shift(1)
    )

    # La première observation n'est pas un changement :
    # elle n'a simplement pas de valeur précédente.
    changement.iloc[0] = False

    dates = (
        heures_paris[
            changement.to_numpy()
        ]
        .tz_localize(None)
        .normalize()
    )

    return set(
        pd.Timestamp(date)
        for date in dates
    )


def filtrer_jours_changement_heure(
    predictions: pd.DataFrame,
    fuseau: str = "Europe/Paris",
) -> pd.DataFrame:
    """
    Exclut uniquement des métriques les jours de changement d'heure.

    Les observations originales ne sont pas modifiées.

    Le paramètre fuseau est volontairement limité à Europe/Paris,
    qui est le fuseau défini par le protocole du projet.
    """

    if fuseau != "Europe/Paris":
        raise ValueError(
            "Le protocole du projet utilise uniquement "
            "le fuseau Europe/Paris."
        )

    verifier_colonnes(
        predictions,
        [
            COLONNE_JOUR,
        ],
    )

    if predictions.empty:
        raise ValueError(
            "Aucune prédiction disponible."
        )

    jours = _normaliser_jour(
        predictions[
            COLONNE_JOUR
        ]
    )

    annee_debut = int(
        jours.dt.year.min()
    )

    annee_fin = int(
        jours.dt.year.max()
    )

    jours_dst = (
        jours_changement_heure_paris(
            annee_debut,
            annee_fin,
        )
    )

    masque = (
        ~jours.isin(
            jours_dst
        )
    )

    return predictions.loc[
        masque
    ].copy()


# ============================================================
# Métriques
# ============================================================

def calculer_metriques(
    predictions: pd.DataFrame,
) -> dict[str, float]:
    """
    MAE et RMSE horaires.

    Aucun filtrage DST n'est appliqué ici afin de conserver
    le comportement historique de la validation 2023.

    Pour l'évaluation finale, utiliser calculer_metriques_finales().
    """

    verifier_colonnes(
        predictions,
        [
            COLONNE_CIBLE,
            "prediction_MW",
        ],
    )

    y = predictions[
        COLONNE_CIBLE
    ].to_numpy()

    y_pred = predictions[
        "prediction_MW"
    ].to_numpy()

    return {
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


def calculer_metriques_journalieres(
    predictions: pd.DataFrame,
) -> dict[str, float]:
    """
    Métriques quotidiennes sur les journées de 24 lignes uniquement.

    Aucun filtrage DST explicite n'est appliqué ici afin de
    conserver le comportement historique.

    Pour le test final, les jours DST sont filtrés avant l'appel.
    """

    verifier_colonnes(
        predictions,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            "prediction_MW",
        ],
    )

    tailles = (
        predictions
        .groupby(
            COLONNE_JOUR
        )
        .size()
    )

    jours_complets = tailles[
        tailles == 24
    ].index

    complet = predictions.loc[
        predictions[
            COLONNE_JOUR
        ].isin(
            jours_complets
        )
    ].copy()

    if complet.empty:
        raise ValueError(
            "Aucune journée complète disponible."
        )

    groupes = complet.groupby(
        COLONNE_JOUR,
        sort=True,
    )

    total_reel = groupes[
        COLONNE_CIBLE
    ].sum()

    total_pred = groupes[
        "prediction_MW"
    ].sum()

    pointe_reelle = groupes[
        COLONNE_CIBLE
    ].max()

    pointe_predite = groupes[
        "prediction_MW"
    ].max()

    heures_reelles = (
        complet.loc[
            groupes[
                COLONNE_CIBLE
            ].idxmax(),
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
            ],
        ]
        .set_index(
            COLONNE_JOUR
        )[
            COLONNE_HEURE
        ]
    )

    heures_predites = (
        complet.loc[
            groupes[
                "prediction_MW"
            ].idxmax(),
            [
                COLONNE_JOUR,
                COLONNE_HEURE,
            ],
        ]
        .set_index(
            COLONNE_JOUR
        )[
            COLONNE_HEURE
        ]
    )

    return {
        "MAE_total_journalier_MWh": float(
            (
                total_pred
                - total_reel
            ).abs().mean()
        ),
        "MAE_pointe_MW": float(
            (
                pointe_predite
                - pointe_reelle
            ).abs().mean()
        ),
        "MAE_heure_pointe_h": float(
            (
                heures_predites
                - heures_reelles
            ).abs().mean()
        ),
        "nb_jours_complets": int(
            len(
                jours_complets
            )
        ),
    }


def calculer_metriques_finales(
    predictions: pd.DataFrame,
) -> dict[str, float]:
    """
    Calcule les métriques finales après exclusion explicite
    des journées de changement d'heure Europe/Paris.

    Les jours DST sont exclus :
    - de la MAE horaire ;
    - de la RMSE horaire ;
    - des métriques quotidiennes.

    Les observations restent toutefois présentes dans les
    prédictions et dans l'historique disponible pour les
    ré-estimations suivantes.
    """

    predictions_evaluees = (
        filtrer_jours_changement_heure(
            predictions
        )
    )

    metriques = calculer_metriques(
        predictions_evaluees
    )

    metriques.update(
        calculer_metriques_journalieres(
            predictions_evaluees
        )
    )

    # Jours de changement d'heure de la période couverte : ils ne sont jamais
    # notés, qu'ils aient été retirés dès la construction du dataset
    # (features.construire_dataset) ou par le filtre ci-dessus.
    jours = _normaliser_jour(
        predictions[
            COLONNE_JOUR
        ]
    )

    jours_dst = jours_changement_heure_paris(
        int(jours.dt.year.min()),
        int(jours.dt.year.max()),
    )

    metriques[
        "nb_jours_dst_exclus"
    ] = int(
        sum(
            jours.min() <= jour <= jours.max()
            for jour in jours_dst
        )
    )

    metriques[
        "nb_observations_evaluees"
    ] = int(
        len(
            predictions_evaluees
        )
    )

    return metriques


# ============================================================
# Validation chronologique 2023
# ============================================================

BLOCS_VALIDATION_2023 = [
    (
        "T1",
        pd.Timestamp(
            "2023-01-01"
        ),
        pd.Timestamp(
            "2023-04-01"
        ),
    ),
    (
        "T2",
        pd.Timestamp(
            "2023-04-01"
        ),
        pd.Timestamp(
            "2023-07-01"
        ),
    ),
    (
        "T3",
        pd.Timestamp(
            "2023-07-01"
        ),
        pd.Timestamp(
            "2023-10-01"
        ),
    ),
    (
        "T4",
        pd.Timestamp(
            "2023-10-01"
        ),
        pd.Timestamp(
            "2024-01-01"
        ),
    ),
]


def valider_m1_expanding(
    donnees: pd.DataFrame,
) -> ResultatValidation:
    """
    Validation chronologique 2023 en quatre blocs trimestriels.

    Pour chaque bloc :
    1. on utilise uniquement les cibles antérieures au bloc ;
    2. on ajuste les 24 modèles ;
    3. on prédit uniquement le bloc courant.

    Aucune information du bloc courant ou d'un bloc futur
    n'entre dans son ajustement.

    Le calcul des métriques reste inchangé afin de garantir
    la reproductibilité exacte des résultats de sélection 2023.
    """

    verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            COLONNE_COVID,
            COLONNE_PERIODE,
        ],
    )

    jours = _normaliser_jour(
        donnees[
            COLONNE_JOUR
        ]
    )

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in BLOCS_VALIDATION_2023:

        apprentissage = apprentissage_avant(
            donnees,
            debut,
            periodes_autorisees=(
                PERIODES_AUTORISEES_VALIDATION_EXPANDING
            ),
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

        modeles = ajuster_modeles_m1(
            apprentissage
        )

        predictions = predire_m1(
            modeles,
            validation_bloc,
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

    metriques = calculer_metriques(
        predictions
    )

    metriques.update(
        calculer_metriques_journalieres(
            predictions
        )
    )

    return ResultatValidation(
        predictions=predictions,
        metriques=metriques,
    )


# ============================================================
# Evaluation finale 2024-2025 - protocole figé
# ============================================================

DATE_DEBUT_TEST_FINAL = pd.Timestamp(
    "2024-01-01"
)

DATE_FIN_TEST_FINAL = pd.Timestamp(
    "2026-01-01"
)


def blocs_mensuels_test_final(
) -> list[
    tuple[
        str,
        pd.Timestamp,
        pd.Timestamp,
    ]
]:
    """
    Retourne les 24 blocs mensuels de janvier 2024
    à décembre 2025.
    """

    debuts = pd.date_range(
        DATE_DEBUT_TEST_FINAL,
        DATE_FIN_TEST_FINAL,
        freq="MS",
        inclusive="left",
    )

    return [
        (
            debut.strftime(
                "%Y-%m"
            ),
            debut,
            debut
            + pd.offsets.MonthBegin(
                1
            ),
        )
        for debut in debuts
    ]


BLOCS_TEST_FINAL_2024_2025 = (
    blocs_mensuels_test_final()
)


def evaluer_m1_test_final(
    donnees: pd.DataFrame,
) -> ResultatValidation:
    """
    Evalue M1 sur 2024-2025 avec réentraînement expanding mensuel.

    Le test passé peut entrer dans l'apprentissage, mais uniquement
    si son jour cible est strictement antérieur au début du mois
    prédit.

    Le mois courant et le futur sont donc toujours exclus.

    Les jours de changement d'heure Europe/Paris :
    - restent dans les prédictions ;
    - restent utilisables comme historique pour les mois suivants ;
    - sont exclus uniquement des métriques finales.
    """

    verifier_colonnes(
        donnees,
        [
            COLONNE_JOUR,
            COLONNE_HEURE,
            COLONNE_CIBLE,
            COLONNE_COVID,
            COLONNE_PERIODE,
        ],
    )

    jours = _normaliser_jour(
        donnees[
            COLONNE_JOUR
        ]
    )

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in BLOCS_TEST_FINAL_2024_2025:

        apprentissage = apprentissage_avant(
            donnees,
            debut,
            periodes_autorisees=(
                PERIODES_AUTORISEES_TEST_FINAL
            ),
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

        test_bloc = donnees.loc[
            masque_test
        ].copy()

        if test_bloc.empty:
            raise ValueError(
                f"Bloc de test {nom_bloc} vide."
            )

        test_bloc[
            "bloc_test"
        ] = nom_bloc

        modeles = ajuster_modeles_m1(
            apprentissage
        )

        predictions = predire_m1(
            modeles,
            test_bloc,
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

    metriques = calculer_metriques_finales(
        predictions
    )

    return ResultatValidation(
        predictions=predictions,
        metriques=metriques,
    )


# ============================================================
# Ancienne validation fixe
# ============================================================

def evaluer_m1(
    donnees: pd.DataFrame,
) -> ResultatValidation:
    """
    Validation fixe 2016-2022 -> 2023.

    Cette fonction est conservée pour comparaison et diagnostic.

    Pour la sélection méthodologique, utiliser
    valider_m1_expanding().
    """

    apprentissage = extraire_apprentissage(
        donnees
    )

    validation = extraire_validation(
        donnees
    )

    modeles = ajuster_modeles_m1(
        apprentissage
    )

    predictions = predire_m1(
        modeles,
        validation,
    )

    metriques = calculer_metriques(
        predictions
    )

    metriques.update(
        calculer_metriques_journalieres(
            predictions
        )
    )

    return ResultatValidation(
        predictions=predictions,
        metriques=metriques,
    )