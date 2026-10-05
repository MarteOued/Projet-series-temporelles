"""Diagnostic des valeurs météorologiques restant manquantes.

Ce module analyse les valeurs qui restent manquantes après l'imputation
spatiale adaptative.

Objectifs
---------
1. Vérifier le nombre de valeurs restant manquantes.
2. Identifier les timestamps entièrement vides.
3. Distinguer :
   - les pannes globales du réseau ;
   - les autres valeurs résiduelles.
4. Identifier les séquences temporelles consécutives de valeurs manquantes.
5. Mesurer leur longueur et leur durée.
6. Préparer le choix d'une méthode d'imputation temporelle.

Important
---------
Ce script est uniquement diagnostique.

Aucune température n'est modifiée.
Aucune nouvelle imputation n'est effectuée.
"""

from pathlib import Path

import pandas as pd

from src import config


# =============================================================================
# CONFIGURATION
# =============================================================================

DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

FICHIER_MATRICE_IMPUTEE = (
    DOSSIER_METEO
    / "temperatures_synop_imputees.csv"
)

FICHIER_JOURNAL = (
    DOSSIER_METEO
    / "journal_imputation_synop.csv"
)

FICHIER_SEQUENCES = (
    DOSSIER_METEO
    / "sequences_manquantes_residuelles.csv"
)

FICHIER_VALEURS_RESIDUELLES = (
    DOSSIER_METEO
    / "valeurs_manquantes_residuelles.csv"
)

PAS_HEURES = 3


# =============================================================================
# LECTURE
# =============================================================================

def lire_matrice_imputee():
    """Lit la matrice obtenue après l'imputation spatiale."""

    if not FICHIER_MATRICE_IMPUTEE.exists():
        raise FileNotFoundError(
            "Matrice imputée introuvable : "
            f"{FICHIER_MATRICE_IMPUTEE}"
        )

    matrice = pd.read_csv(
        FICHIER_MATRICE_IMPUTEE,
        index_col=0,
        parse_dates=True,
    )

    matrice.index = pd.to_datetime(
        matrice.index,
        utc=True,
    )

    matrice.index.name = (
        "validity_time"
    )

    # Les codes WMO doivent rester sur 5 caractères.
    matrice.columns = [
        str(colonne).zfill(5)
        for colonne in matrice.columns
    ]

    matrice = (
        matrice
        .sort_index()
    )

    return matrice


def lire_journal():
    """Lit le journal de l'imputation spatiale."""

    if not FICHIER_JOURNAL.exists():
        raise FileNotFoundError(
            "Journal d'imputation introuvable : "
            f"{FICHIER_JOURNAL}"
        )

    journal = pd.read_csv(
        FICHIER_JOURNAL,
    )

    journal[
        "timestamp"
    ] = pd.to_datetime(
        journal["timestamp"],
        utc=True,
    )

    journal[
        "station"
    ] = (
        journal["station"]
        .astype(str)
        .str.zfill(5)
    )

    return journal


# =============================================================================
# EXTRACTION DES VALEURS RESIDUELLES
# =============================================================================

def extraire_valeurs_residuelles(
    matrice,
):
    """Transforme les NaN résiduels en table longue."""

    masque = matrice.isna()

    valeurs = (
        masque
        .stack()
        .loc[lambda x: x]
        .reset_index()
    )

    valeurs.columns = [
        "timestamp",
        "station",
        "manquant",
    ]

    valeurs = valeurs.drop(
        columns="manquant"
    )

    valeurs[
        "station"
    ] = (
        valeurs["station"]
        .astype(str)
        .str.zfill(5)
    )

    return valeurs


# =============================================================================
# TIMESTAMPS COMPLETEMENT VIDES
# =============================================================================

def identifier_timestamps_vides(
    matrice,
):
    """Retourne les timestamps où les 40 stations sont manquantes."""

    masque = (
        matrice
        .isna()
        .all(axis=1)
    )

    return matrice.index[
        masque
    ]


# =============================================================================
# CONSTRUCTION DES SEQUENCES
# =============================================================================

def construire_sequences(
    valeurs_residuelles,
):
    """Construit les séquences consécutives de NaN pour chaque station.

    Deux valeurs manquantes appartiennent à la même séquence si elles sont
    séparées exactement de 3 heures.

    Une séquence de n timestamps correspond à n températures manquantes.
    Sa longueur temporelle sur la grille est donc n * 3 heures.

    Exemple
    -------
    00h, 03h, 06h manquants :

        nombre_points = 3
        duree_grille_heures = 9

    La différence entre le premier et le dernier timestamp vaut seulement
    6 heures. Les deux quantités sont donc conservées séparément.
    """

    if valeurs_residuelles.empty:
        return pd.DataFrame(
            columns=[
                "station",
                "debut",
                "fin",
                "nombre_points",
                "duree_ecoulee_heures",
                "duree_grille_heures",
            ]
        )

    sequences = []

    for station, groupe in (
        valeurs_residuelles
        .groupby("station")
    ):

        dates = (
            groupe["timestamp"]
            .sort_values()
            .drop_duplicates()
            .tolist()
        )

        if not dates:
            continue

        debut = dates[0]
        precedent = dates[0]
        nombre_points = 1

        for date in dates[1:]:

            ecart = (
                date - precedent
            )

            if ecart == pd.Timedelta(
                hours=PAS_HEURES
            ):
                nombre_points += 1

            else:
                fin = precedent

                duree_ecoulee = (
                    fin - debut
                ).total_seconds() / 3600

                sequences.append(
                    {
                        "station": station,
                        "debut": debut,
                        "fin": fin,
                        "nombre_points":
                            nombre_points,
                        "duree_ecoulee_heures":
                            duree_ecoulee,
                        "duree_grille_heures":
                            nombre_points
                            * PAS_HEURES,
                    }
                )

                debut = date
                nombre_points = 1

            precedent = date

        fin = precedent

        duree_ecoulee = (
            fin - debut
        ).total_seconds() / 3600

        sequences.append(
            {
                "station": station,
                "debut": debut,
                "fin": fin,
                "nombre_points":
                    nombre_points,
                "duree_ecoulee_heures":
                    duree_ecoulee,
                "duree_grille_heures":
                    nombre_points
                    * PAS_HEURES,
            }
        )

    resultat = pd.DataFrame(
        sequences
    )

    resultat = resultat.sort_values(
        [
            "nombre_points",
            "station",
            "debut",
        ],
        ascending=[
            False,
            True,
            True,
        ],
    ).reset_index(
        drop=True
    )

    return resultat


# =============================================================================
# CONTEXTE TEMPOREL
# =============================================================================

def ajouter_contexte_temporel(
    sequences,
    matrice,
):
    """Indique si chaque séquence est encadrée par des observations.

    Pour chaque séquence et station, on regarde la température exactement
    3 heures avant et exactement 3 heures après la séquence.

    Cela permet de savoir si une interpolation temporelle entre deux
    observations réellement disponibles est possible.
    """

    resultat = (
        sequences.copy()
    )

    avant_disponible = []
    apres_disponible = []

    temperature_avant = []
    temperature_apres = []

    for ligne in (
        resultat.itertuples(
            index=False
        )
    ):

        station = ligne.station

        date_avant = (
            ligne.debut
            - pd.Timedelta(
                hours=PAS_HEURES
            )
        )

        date_apres = (
            ligne.fin
            + pd.Timedelta(
                hours=PAS_HEURES
            )
        )

        if (
            date_avant
            in matrice.index
        ):
            valeur_avant = (
                matrice.at[
                    date_avant,
                    station,
                ]
            )
        else:
            valeur_avant = pd.NA

        if (
            date_apres
            in matrice.index
        ):
            valeur_apres = (
                matrice.at[
                    date_apres,
                    station,
                ]
            )
        else:
            valeur_apres = pd.NA

        disponible_avant = (
            pd.notna(
                valeur_avant
            )
        )

        disponible_apres = (
            pd.notna(
                valeur_apres
            )
        )

        avant_disponible.append(
            disponible_avant
        )

        apres_disponible.append(
            disponible_apres
        )

        temperature_avant.append(
            valeur_avant
            if disponible_avant
            else None
        )

        temperature_apres.append(
            valeur_apres
            if disponible_apres
            else None
        )

    resultat[
        "observation_avant"
    ] = avant_disponible

    resultat[
        "observation_apres"
    ] = apres_disponible

    resultat[
        "temperature_avant"
    ] = temperature_avant

    resultat[
        "temperature_apres"
    ] = temperature_apres

    resultat[
        "encadree"
    ] = (
        resultat[
            "observation_avant"
        ]
        & resultat[
            "observation_apres"
        ]
    )

    return resultat


# =============================================================================
# AFFICHAGES
# =============================================================================

def afficher_resume_general(
    matrice,
    valeurs_residuelles,
    timestamps_vides,
):
    """Affiche le résumé général des NaN résiduels."""

    print()
    print("=" * 90)
    print(
        "RESUME GENERAL DES TROUS RESIDUELS"
    )
    print("=" * 90)

    nb_valeurs = len(
        valeurs_residuelles
    )

    nb_timestamps = (
        valeurs_residuelles[
            "timestamp"
        ]
        .nunique()
    )

    nb_stations = (
        valeurs_residuelles[
            "station"
        ]
        .nunique()
    )

    nb_vides = len(
        timestamps_vides
    )

    valeurs_timestamps_vides = (
        nb_vides
        * matrice.shape[1]
    )

    autres = (
        nb_valeurs
        - valeurs_timestamps_vides
    )

    print(
        "Valeurs résiduelles :",
        nb_valeurs,
    )

    print(
        "Timestamps concernés :",
        nb_timestamps,
    )

    print(
        "Stations concernées :",
        nb_stations,
    )

    print()
    print(
        "Timestamps entièrement vides :",
        nb_vides,
    )

    print(
        "Valeurs appartenant aux "
        "timestamps entièrement vides :",
        valeurs_timestamps_vides,
    )

    print(
        "Autres valeurs résiduelles :",
        autres,
    )

    if nb_valeurs > 0:
        print(
            "Part due aux timestamps "
            "entièrement vides :",
            f"{100 * valeurs_timestamps_vides / nb_valeurs:.3f} %",
        )


def afficher_timestamps_vides(
    timestamps_vides,
):
    """Affiche tous les timestamps totalement vides."""

    print()
    print("=" * 90)
    print(
        "TIMESTAMPS ENTIEREMENT VIDES"
    )
    print("=" * 90)

    print(
        "Nombre :",
        len(
            timestamps_vides
        ),
    )

    for timestamp in (
        timestamps_vides
    ):
        print(timestamp)


def afficher_autres_trous(
    valeurs_residuelles,
    timestamps_vides,
):
    """Affiche les résidus hors pannes globales."""

    print()
    print("=" * 90)
    print(
        "TROUS HORS TIMESTAMPS "
        "ENTIEREMENT VIDES"
    )
    print("=" * 90)

    autres = (
        valeurs_residuelles[
            ~valeurs_residuelles[
                "timestamp"
            ].isin(
                timestamps_vides
            )
        ]
        .copy()
    )

    print(
        "Nombre de valeurs :",
        len(autres),
    )

    print(
        "Nombre de timestamps :",
        autres[
            "timestamp"
        ].nunique(),
    )

    print(
        "Nombre de stations :",
        autres[
            "station"
        ].nunique(),
    )

    if autres.empty:
        return

    print()
    print(
        "Nombre de valeurs manquantes "
        "par timestamp :"
    )

    print(
        autres
        .groupby(
            "timestamp"
        )
        .size()
        .sort_values(
            ascending=False
        )
        .to_string()
    )

    print()
    print(
        "Détail des stations :"
    )

    for timestamp, groupe in (
        autres
        .groupby(
            "timestamp"
        )
    ):

        stations = (
            groupe["station"]
            .sort_values()
            .tolist()
        )

        print()
        print(timestamp)

        print(
            "  Nombre :",
            len(stations),
        )

        print(
            "  Stations :",
            ", ".join(
                stations
            ),
        )


def afficher_resume_sequences(
    sequences,
):
    """Affiche les statistiques sur les séquences de NaN."""

    print()
    print("=" * 90)
    print(
        "SEQUENCES TEMPORELLES MANQUANTES"
    )
    print("=" * 90)

    print(
        "Nombre total de séquences :",
        len(sequences),
    )

    if sequences.empty:
        return

    print()
    print(
        "Distribution du nombre de points "
        "manquants consécutifs :"
    )

    distribution = (
        sequences[
            "nombre_points"
        ]
        .value_counts()
        .sort_index()
    )

    total_sequences = len(
        sequences
    )

    for longueur, effectif in (
        distribution.items()
    ):

        pourcentage = (
            100
            * effectif
            / total_sequences
        )

        print(
            f"{longueur:>3} point(s) "
            f"= {longueur * PAS_HEURES:>3} h "
            f": {effectif:>4} séquence(s) "
            f"({pourcentage:.3f} %)"
        )

    print()
    print(
        "Résumé de la longueur "
        "des séquences :"
    )

    print(
        sequences[
            "nombre_points"
        ]
        .describe()
        .to_string()
    )

    print()
    print(
        "Longueur maximale :",
        int(
            sequences[
                "nombre_points"
            ].max()
        ),
        "points",
    )

    print(
        "Durée maximale sur la grille :",
        int(
            sequences[
                "duree_grille_heures"
            ].max()
        ),
        "heures",
    )


def afficher_sequences_longues(
    sequences,
):
    """Affiche les séquences les plus longues."""

    print()
    print("=" * 90)
    print(
        "20 SEQUENCES LES PLUS LONGUES"
    )
    print("=" * 90)

    colonnes = [
        "station",
        "debut",
        "fin",
        "nombre_points",
        "duree_grille_heures",
        "observation_avant",
        "observation_apres",
        "encadree",
    ]

    print(
        sequences[
            colonnes
        ]
        .head(20)
        .to_string(
            index=False
        )
    )


def afficher_encadrement(
    sequences,
):
    """Analyse les séquences utilisables pour interpolation."""

    print()
    print("=" * 90)
    print(
        "ENCADREMENT DES SEQUENCES"
    )
    print("=" * 90)

    if sequences.empty:
        return

    nb_total = len(
        sequences
    )

    nb_encadrees = int(
        sequences[
            "encadree"
        ].sum()
    )

    avant_seulement = int(
        (
            sequences[
                "observation_avant"
            ]
            & ~sequences[
                "observation_apres"
            ]
        ).sum()
    )

    apres_seulement = int(
        (
            ~sequences[
                "observation_avant"
            ]
            & sequences[
                "observation_apres"
            ]
        ).sum()
    )

    aucune = int(
        (
            ~sequences[
                "observation_avant"
            ]
            & ~sequences[
                "observation_apres"
            ]
        ).sum()
    )

    print(
        "Séquences totales :",
        nb_total,
    )

    print(
        "Encadrées des deux côtés :",
        nb_encadrees,
        f"({100 * nb_encadrees / nb_total:.3f} %)",
    )

    print(
        "Observation avant seulement :",
        avant_seulement,
    )

    print(
        "Observation après seulement :",
        apres_seulement,
    )

    print(
        "Aucune observation immédiate "
        "autour de la séquence :",
        aucune,
    )

    print()
    print(
        "Séquences encadrées "
        "par longueur :"
    )

    tableau = (
        sequences
        .groupby(
            "nombre_points"
        )
        .agg(
            sequences=(
                "station",
                "size",
            ),
            encadrees=(
                "encadree",
                "sum",
            ),
        )
    )

    tableau[
        "pourcentage_encadrees"
    ] = (
        100
        * tableau[
            "encadrees"
        ]
        / tableau[
            "sequences"
        ]
    )

    print(
        tableau.to_string(
            formatters={
                "pourcentage_encadrees":
                    lambda x: f"{x:.3f}",
            }
        )
    )


# =============================================================================
# CONTROLES
# =============================================================================

def verifier_coherence(
    matrice,
    journal,
    valeurs_residuelles,
    sequences,
):
    """Vérifie la cohérence entre les différents résultats."""

    nb_nan_matrice = int(
        matrice
        .isna()
        .sum()
        .sum()
    )

    assert (
        nb_nan_matrice
        == len(
            valeurs_residuelles
        )
    )

    journal_non_impute = journal[
        journal[
            "temperature_imputee"
        ]
        .isna()
    ]

    assert (
        len(
            journal_non_impute
        )
        == nb_nan_matrice
    )

    # Chaque valeur résiduelle doit appartenir exactement à une séquence.
    nb_points_sequences = int(
        sequences[
            "nombre_points"
        ].sum()
    )

    assert (
        nb_points_sequences
        == nb_nan_matrice
    )

    print()
    print("=" * 90)
    print(
        "CONTROLES DE COHERENCE"
    )
    print("=" * 90)

    print(
        "NaN dans la matrice :",
        nb_nan_matrice,
    )

    print(
        "NaN dans le journal :",
        len(
            journal_non_impute
        ),
    )

    print(
        "Points dans les séquences :",
        nb_points_sequences,
    )

    print(
        "Contrôles : OK"
    )


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sauvegarder_diagnostic(
    valeurs_residuelles,
    sequences,
):
    """Sauvegarde les résultats du diagnostic."""

    DOSSIER_METEO.mkdir(
        parents=True,
        exist_ok=True,
    )

    valeurs_residuelles.to_csv(
        FICHIER_VALEURS_RESIDUELLES,
        index=False,
    )

    sequences.to_csv(
        FICHIER_SEQUENCES,
        index=False,
    )


# =============================================================================
# EXECUTION
# =============================================================================

def main():

    print("=" * 90)
    print(
        "DIAGNOSTIC DES TROUS "
        "METEOROLOGIQUES RESIDUELS"
    )
    print("=" * 90)

    # =========================================================================
    # 1. LECTURE
    # =========================================================================

    print()
    print(
        "Lecture de la matrice imputée..."
    )

    matrice = (
        lire_matrice_imputee()
    )

    journal = (
        lire_journal()
    )

    print()
    print(
        "Dimensions :",
        matrice.shape,
    )

    print(
        "Première date :",
        matrice.index.min(),
    )

    print(
        "Dernière date :",
        matrice.index.max(),
    )

    # =========================================================================
    # 2. EXTRACTION
    # =========================================================================

    valeurs_residuelles = (
        extraire_valeurs_residuelles(
            matrice
        )
    )

    timestamps_vides = (
        identifier_timestamps_vides(
            matrice
        )
    )

    afficher_resume_general(
        matrice,
        valeurs_residuelles,
        timestamps_vides,
    )

    # =========================================================================
    # 3. TIMESTAMPS COMPLETEMENT VIDES
    # =========================================================================

    afficher_timestamps_vides(
        timestamps_vides
    )

    # =========================================================================
    # 4. AUTRES TROUS
    # =========================================================================

    afficher_autres_trous(
        valeurs_residuelles,
        timestamps_vides,
    )

    # =========================================================================
    # 5. SEQUENCES
    # =========================================================================

    sequences = (
        construire_sequences(
            valeurs_residuelles
        )
    )

    sequences = (
        ajouter_contexte_temporel(
            sequences,
            matrice,
        )
    )

    afficher_resume_sequences(
        sequences
    )

    afficher_sequences_longues(
        sequences
    )

    # =========================================================================
    # 6. ENCADREMENT TEMPOREL
    # =========================================================================

    afficher_encadrement(
        sequences
    )

    # =========================================================================
    # 7. CONTROLES
    # =========================================================================

    verifier_coherence(
        matrice,
        journal,
        valeurs_residuelles,
        sequences,
    )

    # =========================================================================
    # 8. SAUVEGARDE
    # =========================================================================

    sauvegarder_diagnostic(
        valeurs_residuelles,
        sequences,
    )

    print()
    print("=" * 90)
    print(
        "FICHIERS CREES"
    )
    print("=" * 90)

    print(
        "Valeurs résiduelles :",
        FICHIER_VALEURS_RESIDUELLES,
    )

    print(
        "Séquences :",
        FICHIER_SEQUENCES,
    )

    print()
    print(
        "Diagnostic terminé."
    )

    print(
        "Aucune nouvelle imputation "
        "n'a été effectuée."
    )


# =============================================================================
# LANCEMENT
# =============================================================================

if __name__ == "__main__":
    main()