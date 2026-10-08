"""
Évaluation finale M4 sur 2024-2025.

IMPORTANT
---------
Ce module est créé après la sélection M4 sur la validation 2023
et avant toute consultation des performances M4 sur 2024-2025.

Configuration définitivement gelée :

    Base : M1
    Correction : ARMA(1,0)
    Configuration : M4-1

Aucun réglage ne doit être effectué à partir des résultats 2024-2025.

Protocole
---------
Le protocole final suit les blocs mensuels expanding déjà définis
pour M1/M2/M3.

Pour chaque bloc mensuel :
    1. apprentissage strictement antérieur au début du bloc ;
    2. ajustement M1 ;
    3. estimation de l'ARMA(1,0) sur les résidus M1 disponibles ;
    4. prédiction M4 du mois ;
    5. passage au mois suivant avec fenêtre croissante.

Les métriques sont calculées :
    - globalement sur 2024-2025 ;
    - séparément sur 2024 ;
    - séparément sur 2025.

Le test final ne devait être exécuté qu'une seule fois. Il l'a été deux fois :
la seconde, le 2026-10-07, uniquement pour corriger une fuite (l'heure 13
utilisait un résidu de M1 pas encore publié à 14 h, voir docs/decisions.md).
Aucun réglage n'a été changé.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src import modeles_arma as m4
from src import modeles_lineaires as m1


# ===========================================================================
# Configuration définitivement gelée
# ===========================================================================

CONFIGURATION_M4_FINALE = "M4-1"

P_FINAL = 1
Q_FINAL = 0

ANNEES_TEST = {
    2024,
    2025,
}


# ===========================================================================
# Fichiers de sortie
# ===========================================================================

DOSSIER_RESULTATS = Path(
    "data/resultats"
)

FICHIER_PREDICTIONS = (
    DOSSIER_RESULTATS
    / "predictions_test_final_m4_2024_2025.csv"
)

FICHIER_METRIQUES = (
    DOSSIER_RESULTATS
    / "test_final_m4_2024_2025.csv"
)


# ===========================================================================
# Résultat
# ===========================================================================

@dataclass
class ResultatTestFinalM4:
    configuration: str
    p: int
    q: int
    predictions: pd.DataFrame
    metriques_globales: dict[str, float]
    metriques_par_annee: pd.DataFrame


# ===========================================================================
# Vérifications du gel
# ===========================================================================

def verifier_configuration_gelee() -> None:
    """
    Vérifie que l'évaluation finale utilise exclusivement M4-1.
    """

    if CONFIGURATION_M4_FINALE != "M4-1":
        raise RuntimeError(
            "La configuration finale M4 doit rester M4-1."
        )

    p, q = m4.verifier_configuration_m4(
        CONFIGURATION_M4_FINALE
    )

    if (
        p != P_FINAL
        or q != Q_FINAL
    ):
        raise RuntimeError(
            "La configuration M4 gelée a été modifiée."
        )

    if (
        P_FINAL,
        Q_FINAL,
    ) != (
        1,
        0,
    ):
        raise RuntimeError(
            "Le test final doit utiliser ARMA(1,0)."
        )


# ===========================================================================
# Métriques
# ===========================================================================

def calculer_metriques_par_annee(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcule les métriques finales séparément pour 2024 et 2025.
    """

    predictions = (
        predictions.copy()
    )

    predictions[
        m4.COLONNE_JOUR
    ] = pd.to_datetime(
        predictions[
            m4.COLONNE_JOUR
        ]
    )

    predictions[
        "annee"
    ] = (
        predictions[
            m4.COLONNE_JOUR
        ]
        .dt.year
    )

    lignes = []

    for annee in sorted(
        ANNEES_TEST
    ):

        donnees_annee = (
            predictions.loc[
                predictions[
                    "annee"
                ]
                == annee
            ]
            .copy()
        )

        if donnees_annee.empty:
            raise RuntimeError(
                f"Aucune prédiction pour {annee}."
            )

        metriques = (
            m1.calculer_metriques_finales(
                donnees_annee
            )
        )

        lignes.append(
            {
                "annee": annee,
                **metriques,
            }
        )

    return pd.DataFrame(
        lignes
    )


# ===========================================================================
# Évaluation finale
# ===========================================================================

def evaluer_m4_test_final(
    donnees: pd.DataFrame,
) -> ResultatTestFinalM4:
    """
    Exécute l'évaluation finale M4 sur 2024-2025.

    ATTENTION :
    cette fonction correspond à l'ouverture du jeu de test final.
    Elle ne doit être lancée qu'après commit du présent fichier.
    """

    verifier_configuration_gelee()

    m4.verifier_donnees_m4(
        donnees
    )

    donnees = (
        donnees.copy()
    )

    donnees[
        m4.COLONNE_JOUR
    ] = pd.to_datetime(
        donnees[
            m4.COLONNE_JOUR
        ]
    ).dt.normalize()

    morceaux = []

    for (
        nom_bloc,
        debut,
        fin,
    ) in m1.BLOCS_TEST_FINAL_2024_2025:

        debut = pd.Timestamp(
            debut
        ).normalize()

        fin = pd.Timestamp(
            fin
        ).normalize()

        # ---------------------------------------------------------------
        # Apprentissage expanding strictement antérieur au mois courant
        # ---------------------------------------------------------------

        apprentissage = (
            m1.apprentissage_avant(
                donnees,
                debut,
                periodes_autorisees=(
                    m1.PERIODES_AUTORISEES_TEST_FINAL
                ),
            )
        )

        if apprentissage.empty:
            raise RuntimeError(
                f"Apprentissage vide pour {nom_bloc}."
            )

        jour_max_apprentissage = (
            pd.to_datetime(
                apprentissage[
                    m4.COLONNE_JOUR
                ]
            )
            .max()
            .normalize()
        )

        if (
            jour_max_apprentissage
            >= debut
        ):
            raise RuntimeError(
                "Fuite temporelle détectée dans "
                f"{nom_bloc} : "
                f"max apprentissage = "
                f"{jour_max_apprentissage}, "
                f"début bloc = {debut}."
            )

        # ---------------------------------------------------------------
        # Bloc de test
        # ---------------------------------------------------------------

        masque_test = (
            (
                donnees[
                    m1.COLONNE_PERIODE
                ]
                == "test"
            )
            & (
                donnees[
                    m4.COLONNE_JOUR
                ]
                >= debut
            )
            & (
                donnees[
                    m4.COLONNE_JOUR
                ]
                < fin
            )
        )

        test_bloc = (
            donnees.loc[
                masque_test
            ]
            .copy()
        )

        if test_bloc.empty:
            raise RuntimeError(
                f"Bloc de test vide : {nom_bloc}."
            )

        # ---------------------------------------------------------------
        # M4 gelé : M1 + ARMA(1,0)
        # ---------------------------------------------------------------

        predictions = (
            m4.predire_bloc_m4(
                apprentissage=apprentissage,
                bloc=test_bloc,
                p=P_FINAL,
                q=Q_FINAL,
            )
        )

        predictions[
            "bloc_test"
        ] = nom_bloc

        morceaux.append(
            predictions
        )

    # ===================================================================
    # Assemblage
    # ===================================================================

    if not morceaux:
        raise RuntimeError(
            "Aucune prédiction finale M4 produite."
        )

    predictions = (
        pd.concat(
            morceaux,
            ignore_index=True,
        )
        .sort_values(
            [
                m4.COLONNE_JOUR,
                m4.COLONNE_HEURE,
            ]
        )
        .reset_index(
            drop=True
        )
    )

    # ===================================================================
    # Contrôles finaux
    # ===================================================================

    if len(
        predictions
    ) != 17448:
        raise RuntimeError(
            "Le test final M4 doit contenir "
            "17448 observations, contre "
            f"{len(predictions)}."
        )

    if predictions[
        m4.COLONNE_PREDICTION_M4
    ].isna().any():
        raise RuntimeError(
            "NaN dans les prédictions finales M4."
        )

    if predictions.duplicated(
        [
            m4.COLONNE_JOUR,
            m4.COLONNE_HEURE,
        ]
    ).any():
        raise RuntimeError(
            "Doublons jour/heure dans le test final M4."
        )

    annees = set(
        predictions[
            m4.COLONNE_JOUR
        ]
        .dt.year
        .unique()
    )

    if annees != ANNEES_TEST:
        raise RuntimeError(
            "Années inattendues dans le test final : "
            f"{annees}."
        )

    periodes = set(
        donnees.loc[
            donnees[
                m4.COLONNE_JOUR
            ].isin(
                predictions[
                    m4.COLONNE_JOUR
                ]
            ),
            m1.COLONNE_PERIODE,
        ].unique()
    )

    if periodes != {
        "test"
    }:
        raise RuntimeError(
            "Le test final contient une période "
            f"inattendue : {periodes}."
        )

    # ===================================================================
    # Métriques
    # ===================================================================

    metriques_globales = (
        m1.calculer_metriques_finales(
            predictions
        )
    )

    metriques_par_annee = (
        calculer_metriques_par_annee(
            predictions
        )
    )

    return ResultatTestFinalM4(
        configuration=(
            CONFIGURATION_M4_FINALE
        ),
        p=P_FINAL,
        q=Q_FINAL,
        predictions=predictions,
        metriques_globales=(
            metriques_globales
        ),
        metriques_par_annee=(
            metriques_par_annee
        ),
    )


# ===========================================================================
# Sauvegarde
# ===========================================================================

def sauvegarder_resultats(
    resultat: ResultatTestFinalM4,
) -> None:
    """
    Sauvegarde les prédictions et les métriques du test final.
    """

    DOSSIER_RESULTATS.mkdir(
        parents=True,
        exist_ok=True,
    )

    resultat.predictions.to_csv(
        FICHIER_PREDICTIONS,
        index=False,
    )

    lignes = []

    for ligne in (
        resultat
        .metriques_par_annee
        .to_dict(
            orient="records"
        )
    ):

        lignes.append(
            {
                "periode": str(
                    int(
                        ligne.pop(
                            "annee"
                        )
                    )
                ),
                **ligne,
            }
        )

    lignes.append(
        {
            "periode": "2024-2025",
            **resultat.metriques_globales,
        }
    )

    pd.DataFrame(
        lignes
    ).to_csv(
        FICHIER_METRIQUES,
        index=False,
    )


# ===========================================================================
# Affichage
# ===========================================================================

def afficher_resultats(
    resultat: ResultatTestFinalM4,
) -> None:
    """
    Affiche un résumé lisible du test final.
    """

    print(
        "=" * 80
    )

    print(
        "TEST FINAL M4 - 2024-2025"
    )

    print(
        "=" * 80
    )

    print()

    print(
        "Configuration :",
        resultat.configuration,
    )

    print(
        "ARMA :",
        f"({resultat.p},{resultat.q})",
    )

    print(
        "Nombre de predictions :",
        len(
            resultat.predictions
        ),
    )

    print()

    print(
        "=" * 80
    )

    print(
        "RESULTATS PAR ANNEE"
    )

    print(
        "=" * 80
    )

    print(
        resultat
        .metriques_par_annee
        .to_string(
            index=False
        )
    )

    print()

    print(
        "=" * 80
    )

    print(
        "RESULTATS GLOBAUX 2024-2025"
    )

    print(
        "=" * 80
    )

    print(
        pd.Series(
            resultat.metriques_globales
        ).to_string()
    )

    print()

    print(
        "Predictions :",
        FICHIER_PREDICTIONS,
    )

    print(
        "Metriques :",
        FICHIER_METRIQUES,
    )


# ===========================================================================
# Programme principal
# ===========================================================================

def main() -> None:
    """
    Charge le dataset et exécute le test final M4.
    """

    fichier_dataset = Path(
        "data/donnees-preparees/"
        "dataset_modelisation_2016_2025.csv"
    )

    if not fichier_dataset.exists():
        raise FileNotFoundError(
            f"Dataset absent : {fichier_dataset}"
        )

    donnees = pd.read_csv(
        fichier_dataset
    )

    resultat = (
        evaluer_m4_test_final(
            donnees
        )
    )

    sauvegarder_resultats(
        resultat
    )

    afficher_resultats(
        resultat
    )


if __name__ == "__main__":
    main()