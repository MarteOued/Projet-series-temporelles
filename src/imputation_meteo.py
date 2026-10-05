"""Imputation définitive des températures SYNOP manquantes.

La méthode utilisée a été sélectionnée à l'aide du benchmark défini dans
``src.benchmark_imputation`` :

    régression spatiale adaptative sur les 3 stations les plus corrélées.

Principe
--------
Pour chaque station :

1. identifier ses 3 stations les plus corrélées ;
2. ajuster les modèles de régression correspondant aux différentes
   combinaisons possibles de ces voisins ;
3. pour chaque température réellement manquante :
       - utiliser 3 voisins s'ils sont disponibles ;
       - sinon 2 voisins ;
       - sinon 1 voisin ;
       - sinon laisser la valeur manquante.

Important
---------
Contrairement au benchmark, les modèles sont ici ajustés sur toute la matrice
originale disponible. Aucune valeur observée n'est artificiellement masquée.

Les températures réellement observées ne sont jamais modifiées.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.benchmark_imputation import (
    NB_VOISINS,
    ajuster_modeles_adaptatifs,
    calculer_correlations,
    construire_matrice_temperatures,
    k_stations_plus_correlees,
)
from src.config import DATA_BRUTES


# =============================================================================
# CONFIGURATION
# =============================================================================

DOSSIER_SORTIE = DATA_BRUTES.parent / "donnees-traitees" / "meteo"

FICHIER_MATRICE_ORIGINALE = (
    DOSSIER_SORTIE
    / "temperatures_synop_originales.csv"
)

FICHIER_MATRICE_IMPUTEE = (
    DOSSIER_SORTIE
    / "temperatures_synop_imputees.csv"
)

FICHIER_JOURNAL_IMPUTATION = (
    DOSSIER_SORTIE
    / "journal_imputation_synop.csv"
)


# =============================================================================
# POSITIONS REELLEMENT MANQUANTES
# =============================================================================

def extraire_valeurs_manquantes(matrice):
    """Retourne les positions réellement manquantes de la matrice.

    Retour
    ------
    pandas.DataFrame
        Colonnes :
        - timestamp
        - station
    """

    masque = matrice.isna()

    lignes, colonnes = np.where(
        masque.to_numpy()
    )

    valeurs_manquantes = pd.DataFrame(
        {
            "timestamp": matrice.index[
                lignes
            ],
            "station": matrice.columns[
                colonnes
            ],
        }
    )

    return valeurs_manquantes


# =============================================================================
# IMPUTATION ADAPTATIVE
# =============================================================================

def imputer_valeurs_manquantes(
    matrice,
    valeurs_manquantes,
    modeles_adaptatifs,
):
    """Impute les valeurs manquantes avec les modèles adaptatifs.

    La fonction travaille sur une copie de la matrice originale.

    Les valeurs observées ne sont jamais modifiées.

    Une prédiction est produite avec le modèle utilisant le plus grand
    nombre de voisins disponibles parmi les trois meilleurs voisins.

    Important
    ---------
    Les voisins sont lus dans la matrice originale et non dans la matrice
    progressivement imputée.

    Cela évite qu'une valeur prédite soit ensuite utilisée comme donnée
    explicative pour prédire une autre valeur.
    """

    matrice_imputee = matrice.copy()

    journal = []

    for ligne in valeurs_manquantes.itertuples(
        index=False
    ):

        timestamp = ligne.timestamp
        station = ligne.station

        modeles_station = (
            modeles_adaptatifs.get(
                station
            )
        )

        prediction = np.nan
        voisins_utilises = ""
        nombre_voisins = 0

        if modeles_station:

            for combinaison, modele in (
                modeles_station.items()
            ):

                voisins = list(
                    combinaison
                )

                temperatures = (
                    matrice.loc[
                        timestamp,
                        voisins,
                    ]
                )

                if temperatures.notna().all():

                    x = temperatures.to_numpy(
                        dtype=float
                    )

                    prediction = (
                        modele["intercept"]
                        + np.dot(
                            modele["coefficients"],
                            x,
                        )
                    )

                    prediction = float(
                        prediction
                    )

                    voisins_utilises = (
                        ",".join(
                            voisins
                        )
                    )

                    nombre_voisins = len(
                        voisins
                    )

                    break

        if pd.notna(prediction):

            matrice_imputee.at[
                timestamp,
                station,
            ] = prediction

        journal.append(
            {
                "timestamp": timestamp,
                "station": station,
                "temperature_imputee":
                    prediction,
                "voisins_utilises":
                    voisins_utilises,
                "nombre_voisins":
                    nombre_voisins,
            }
        )

    journal = pd.DataFrame(
        journal
    )

    return (
        matrice_imputee,
        journal,
    )


# =============================================================================
# CONTROLES
# =============================================================================

def verifier_imputation(
    matrice_originale,
    matrice_imputee,
    journal,
):
    """Effectue les contrôles de cohérence de l'imputation."""

    # -------------------------------------------------------------------------
    # Dimensions
    # -------------------------------------------------------------------------

    assert (
        matrice_originale.shape
        == matrice_imputee.shape
    )

    assert (
        matrice_originale.index.equals(
            matrice_imputee.index
        )
    )

    assert (
        matrice_originale.columns.equals(
            matrice_imputee.columns
        )
    )

    # -------------------------------------------------------------------------
    # Valeurs observées
    # -------------------------------------------------------------------------

    masque_observe = (
        matrice_originale.notna()
    )

    originales_observees = (
        matrice_originale
        .where(masque_observe)
        .stack()
        .sort_index()
    )

    imputees_observees = (
        matrice_imputee
        .where(masque_observe)
        .stack()
        .sort_index()
    )

    assert np.allclose(
        originales_observees.to_numpy(),
        imputees_observees.to_numpy(),
        rtol=0,
        atol=0,
        equal_nan=True,
    )

    # -------------------------------------------------------------------------
    # Journal
    # -------------------------------------------------------------------------

    nb_manquantes_originales = int(
        matrice_originale
        .isna()
        .sum()
        .sum()
    )

    assert (
        len(journal)
        == nb_manquantes_originales
    )

    nb_imputees = int(
        journal[
            "temperature_imputee"
        ]
        .notna()
        .sum()
    )

    nb_restantes = int(
        matrice_imputee
        .isna()
        .sum()
        .sum()
    )

    assert (
        nb_imputees
        + nb_restantes
        == nb_manquantes_originales
    )

    # -------------------------------------------------------------------------
    # Aucun 0 voisin ne doit avoir de prédiction
    # -------------------------------------------------------------------------

    cas_zero = journal[
        journal[
            "nombre_voisins"
        ] == 0
    ]

    assert (
        cas_zero[
            "temperature_imputee"
        ]
        .isna()
        .all()
    )

    # -------------------------------------------------------------------------
    # Toute prédiction doit utiliser au moins un voisin
    # -------------------------------------------------------------------------

    cas_predits = journal[
        journal[
            "temperature_imputee"
        ]
        .notna()
    ]

    assert (
        cas_predits[
            "nombre_voisins"
        ]
        .between(
            1,
            NB_VOISINS,
        )
        .all()
    )

    return {
        "nb_manquantes_originales":
            nb_manquantes_originales,
        "nb_imputees":
            nb_imputees,
        "nb_restantes":
            nb_restantes,
    }


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sauvegarder_resultats(
    matrice_originale,
    matrice_imputee,
    journal,
):
    """Sauvegarde les matrices et le journal d'imputation."""

    DOSSIER_SORTIE.mkdir(
        parents=True,
        exist_ok=True,
    )

    matrice_originale.to_csv(
        FICHIER_MATRICE_ORIGINALE,
        index=True,
    )

    matrice_imputee.to_csv(
        FICHIER_MATRICE_IMPUTEE,
        index=True,
    )

    journal.to_csv(
        FICHIER_JOURNAL_IMPUTATION,
        index=False,
    )


# =============================================================================
# AFFICHAGE DES RESULTATS
# =============================================================================

def afficher_repartition_voisins(
    journal,
):
    """Affiche la répartition des imputations par nombre de voisins."""

    print()
    print("=" * 90)
    print(
        "NOMBRE DE VOISINS UTILISES "
        "POUR LES VALEURS REELLES"
    )
    print("=" * 90)

    repartition = (
        journal[
            "nombre_voisins"
        ]
        .value_counts()
        .reindex(
            [3, 2, 1, 0],
            fill_value=0,
        )
    )

    total = len(
        journal
    )

    for nb_voisins, effectif in (
        repartition.items()
    ):

        pourcentage = (
            100
            * effectif
            / total
        )

        print(
            f"{nb_voisins} voisin(s) : "
            f"{effectif} "
            f"({pourcentage:.3f} %)"
        )


def afficher_valeurs_restantes(
    matrice_imputee,
    journal,
):
    """Décrit les valeurs qui n'ont pas pu être imputées."""

    restantes = journal[
        journal[
            "temperature_imputee"
        ]
        .isna()
    ].copy()

    print()
    print("=" * 90)
    print(
        "VALEURS RESTANT MANQUANTES"
    )
    print("=" * 90)

    print(
        "Nombre :",
        len(restantes),
    )

    if restantes.empty:
        print(
            "Toutes les valeurs "
            "ont été imputées."
        )
        return

    timestamps_restants = (
        restantes[
            "timestamp"
        ]
        .nunique()
    )

    stations_restantes = (
        restantes[
            "station"
        ]
        .nunique()
    )

    print(
        "Nombre de timestamps concernés :",
        timestamps_restants,
    )

    print(
        "Nombre de stations concernées :",
        stations_restantes,
    )

    # Timestamps complètement vides dans la matrice originale/imputée
    timestamps_vides = (
        matrice_imputee
        .isna()
        .all(axis=1)
    )

    print(
        "Timestamps encore entièrement vides :",
        int(
            timestamps_vides.sum()
        ),
    )

    print()
    print(
        "Répartition des valeurs restantes "
        "par timestamp :"
    )

    resume_timestamp = (
        restantes
        .groupby(
            "timestamp"
        )
        .size()
        .sort_values(
            ascending=False
        )
    )

    print(
        resume_timestamp
        .head(20)
        .to_string()
    )

    print()
    print(
        "Répartition des valeurs restantes "
        "par station :"
    )

    resume_station = (
        restantes
        .groupby(
            "station"
        )
        .size()
        .sort_values(
            ascending=False
        )
    )

    print(
        resume_station
        .head(20)
        .to_string()
    )


# =============================================================================
# EXECUTION
# =============================================================================

def main():

    print("=" * 90)
    print(
        "IMPUTATION DEFINITIVE "
        "DES TEMPERATURES SYNOP"
    )
    print("=" * 90)

    # =========================================================================
    # 1. MATRICE ORIGINALE
    # =========================================================================

    print()
    print(
        "Construction de la matrice originale..."
    )

    matrice, stations = (
        construire_matrice_temperatures()
    )

    nb_manquantes_avant = int(
        matrice
        .isna()
        .sum()
        .sum()
    )

    print()
    print(
        "Dimensions :",
        matrice.shape,
    )

    print(
        "Valeurs manquantes avant imputation :",
        nb_manquantes_avant,
    )

    print(
        "Pourcentage manquant :",
        f"{100 * nb_manquantes_avant / matrice.size:.4f} %",
    )

    assert matrice.shape == (
        29472,
        40,
    )

    assert (
        nb_manquantes_avant
        == 11285
    )

    # =========================================================================
    # 2. POSITIONS A IMPUTER
    # =========================================================================

    print()
    print(
        "Identification des valeurs "
        "réellement manquantes..."
    )

    valeurs_manquantes = (
        extraire_valeurs_manquantes(
            matrice
        )
    )

    print(
        "Positions à traiter :",
        len(
            valeurs_manquantes
        ),
    )

    assert (
        len(valeurs_manquantes)
        == nb_manquantes_avant
    )

    # =========================================================================
    # 3. CORRELATIONS SUR LES DONNEES REELLES
    # =========================================================================

    print()
    print(
        "Calcul des corrélations "
        "sur les données originales..."
    )

    correlations = (
        calculer_correlations(
            matrice
        )
    )

    voisins_multi = (
        k_stations_plus_correlees(
            correlations,
            k=NB_VOISINS,
        )
    )

    # =========================================================================
    # 4. REENTRAINEMENT DES MODELES
    # =========================================================================

    print()
    print(
        "Réentraînement des modèles "
        "sur les données originales..."
    )

    modeles_adaptatifs = (
        ajuster_modeles_adaptatifs(
            matrice,
            voisins_multi,
        )
    )

    nb_modeles = sum(
        len(modeles)
        for modeles
        in modeles_adaptatifs.values()
    )

    print(
        "Stations avec modèles :",
        len(
            modeles_adaptatifs
        ),
    )

    print(
        "Nombre total de sous-modèles :",
        nb_modeles,
    )

    assert (
        len(modeles_adaptatifs)
        == 40
    )

    # =========================================================================
    # 5. IMPUTATION
    # =========================================================================

    print()
    print(
        "Imputation des valeurs "
        "réellement manquantes..."
    )

    matrice_imputee, journal = (
        imputer_valeurs_manquantes(
            matrice,
            valeurs_manquantes,
            modeles_adaptatifs,
        )
    )

    # =========================================================================
    # 6. CONTROLES
    # =========================================================================

    print()
    print(
        "Contrôle de l'imputation..."
    )

    bilan = verifier_imputation(
        matrice,
        matrice_imputee,
        journal,
    )

    nb_imputees = bilan[
        "nb_imputees"
    ]

    nb_restantes = bilan[
        "nb_restantes"
    ]

    couverture = (
        100
        * nb_imputees
        / nb_manquantes_avant
    )

    print()
    print("=" * 90)
    print(
        "BILAN DE L'IMPUTATION"
    )
    print("=" * 90)

    print(
        "Valeurs manquantes initiales :",
        nb_manquantes_avant,
    )

    print(
        "Valeurs imputées :",
        nb_imputees,
    )

    print(
        "Valeurs restant manquantes :",
        nb_restantes,
    )

    print(
        "Couverture de l'imputation :",
        f"{couverture:.3f} %",
    )

    # =========================================================================
    # 7. REPARTITION DES VOISINS
    # =========================================================================

    afficher_repartition_voisins(
        journal
    )

    # =========================================================================
    # 8. VALEURS RESTANTES
    # =========================================================================

    afficher_valeurs_restantes(
        matrice_imputee,
        journal,
    )

    # =========================================================================
    # 9. EXEMPLES D'IMPUTATIONS
    # =========================================================================

    print()
    print("=" * 90)
    print(
        "20 EXEMPLES D'IMPUTATIONS"
    )
    print("=" * 90)

    exemples = (
        journal[
            journal[
                "temperature_imputee"
            ].notna()
        ]
        .head(20)
    )

    print(
        exemples.to_string(
            index=False
        )
    )

    # =========================================================================
    # 10. SAUVEGARDE
    # =========================================================================

    print()
    print(
        "Sauvegarde des résultats..."
    )

    sauvegarder_resultats(
        matrice,
        matrice_imputee,
        journal,
    )

    print()
    print("=" * 90)
    print(
        "FICHIERS CREES"
    )
    print("=" * 90)

    print(
        "Matrice originale :",
        FICHIER_MATRICE_ORIGINALE,
    )

    print(
        "Matrice imputée :",
        FICHIER_MATRICE_IMPUTEE,
    )

    print(
        "Journal :",
        FICHIER_JOURNAL_IMPUTATION,
    )

    print()
    print(
        "Imputation terminée avec succès."
    )


# =============================================================================
# LANCEMENT
# =============================================================================

if __name__ == "__main__":
    main()