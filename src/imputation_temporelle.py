"""
Imputation temporelle finale des températures SYNOP.

Ce script intervient APRES l'imputation spatiale.

Principe retenu à partir du benchmark temporel :
    - trou de 1 point  (3 h)  : interpolation linéaire ;
    - trou de 2 points (6 h)  : méthode hybride ;
    - trou de 3 points (9 h)  : méthode hybride ;
    - trou de 8 points (24 h) : méthode journalière +/- 24 h.

La méthode hybride est la moyenne entre :
    - l'interpolation linéaire ;
    - l'estimation journalière +/- 24 h.

Le script :
    1. lit la matrice après imputation spatiale ;
    2. détecte les séquences manquantes ;
    3. choisit la méthode selon leur longueur ;
    4. impute uniquement les NaN résiduels ;
    5. conserve toutes les valeurs déjà présentes ;
    6. crée un journal des imputations temporelles ;
    7. sauvegarde la matrice finale.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# CONFIGURATION
# =============================================================================

RACINE_PROJET = Path(__file__).resolve().parents[1]

DOSSIER_METEO = (
    RACINE_PROJET
    / "data"
    / "donnees-traitees"
    / "meteo"
)

FICHIER_ENTREE = (
    DOSSIER_METEO
    / "temperatures_synop_imputees.csv"
)

FICHIER_SORTIE = (
    DOSSIER_METEO
    / "temperatures_synop_completes.csv"
)

FICHIER_JOURNAL = (
    DOSSIER_METEO
    / "journal_imputation_temporelle.csv"
)


# =============================================================================
# OUTILS
# =============================================================================

def titre(texte):
    """Affiche un titre."""
    print("\n" + "=" * 90)
    print(texte)
    print("=" * 90)


def lire_matrice():
    """
    Lit la matrice obtenue après l'imputation spatiale.
    """

    if not FICHIER_ENTREE.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {FICHIER_ENTREE}"
        )

    df = pd.read_csv(
        FICHIER_ENTREE,
        index_col=0,
        parse_dates=True
    )

    df.index = pd.to_datetime(
        df.index,
        utc=True
    )

    df = df.sort_index()

    # Les identifiants WMO doivent rester des chaînes.
    df.columns = [
        str(col).zfill(5)
        for col in df.columns
    ]

    return df


# =============================================================================
# DETECTION DES SEQUENCES MANQUANTES
# =============================================================================

def detecter_sequences_manquantes(serie):
    """
    Détecte les séquences consécutives de NaN dans une série.

    Retour
    ------
    list[dict]
        Chaque dictionnaire contient :
        - debut_pos
        - fin_pos
        - longueur
    """

    masque = serie.isna().to_numpy()

    sequences = []

    debut = None

    for i, manquant in enumerate(masque):

        if manquant and debut is None:
            debut = i

        fin_de_sequence = (
            debut is not None
            and (
                not manquant
                or i == len(masque) - 1
            )
        )

        if fin_de_sequence:

            if manquant and i == len(masque) - 1:
                fin = i
            else:
                fin = i - 1

            sequences.append(
                {
                    "debut_pos": debut,
                    "fin_pos": fin,
                    "longueur": fin - debut + 1,
                }
            )

            debut = None

    return sequences


# =============================================================================
# METHODE 1 : INTERPOLATION LINEAIRE
# =============================================================================

def prediction_lineaire(
    serie_reference,
    debut_pos,
    fin_pos
):
    """
    Interpolation linéaire entre l'observation précédant
    le trou et l'observation suivant le trou.

    Important :
    la série de référence n'est pas modifiée pendant
    le calcul.
    """

    n = len(serie_reference)

    pos_avant = debut_pos - 1
    pos_apres = fin_pos + 1

    if pos_avant < 0 or pos_apres >= n:
        return None

    valeur_avant = serie_reference.iloc[pos_avant]
    valeur_apres = serie_reference.iloc[pos_apres]

    if pd.isna(valeur_avant) or pd.isna(valeur_apres):
        return None

    longueur = fin_pos - debut_pos + 1

    predictions = []

    for k in range(1, longueur + 1):

        poids = k / (longueur + 1)

        prediction = (
            valeur_avant
            + poids
            * (valeur_apres - valeur_avant)
        )

        predictions.append(float(prediction))

    return predictions


# =============================================================================
# METHODE 2 : JOURNALIERE +/- 24 H
# =============================================================================

def prediction_journaliere(
    serie_reference,
    debut_pos,
    fin_pos
):
    """
    Pour chaque timestamp manquant, utilise :

        T(t - 24 h)
        T(t + 24 h)

    et prend leur moyenne.

    Si une seule des deux valeurs est disponible,
    elle est utilisée seule.

    Si aucune n'est disponible, la prédiction
    est impossible pour ce point.
    """

    index = serie_reference.index

    predictions = []

    for pos in range(debut_pos, fin_pos + 1):

        timestamp = index[pos]

        timestamp_avant = (
            timestamp
            - pd.Timedelta(hours=24)
        )

        timestamp_apres = (
            timestamp
            + pd.Timedelta(hours=24)
        )

        valeurs = []

        if timestamp_avant in index:

            valeur = serie_reference.loc[
                timestamp_avant
            ]

            if pd.notna(valeur):
                valeurs.append(float(valeur))

        if timestamp_apres in index:

            valeur = serie_reference.loc[
                timestamp_apres
            ]

            if pd.notna(valeur):
                valeurs.append(float(valeur))

        if len(valeurs) == 0:
            predictions.append(np.nan)

        else:
            predictions.append(
                float(np.mean(valeurs))
            )

    return predictions


# =============================================================================
# METHODE 3 : HYBRIDE
# =============================================================================

def prediction_hybride(
    serie_reference,
    debut_pos,
    fin_pos
):
    """
    Combine :

        interpolation linéaire
        +
        estimation journalière +/- 24 h

    La prédiction hybride est leur moyenne lorsque
    les deux sont disponibles.

    Si une seule méthode est disponible, elle est
    utilisée comme repli.
    """

    pred_lineaire = prediction_lineaire(
        serie_reference,
        debut_pos,
        fin_pos
    )

    pred_journaliere = prediction_journaliere(
        serie_reference,
        debut_pos,
        fin_pos
    )

    longueur = fin_pos - debut_pos + 1

    predictions = []

    for i in range(longueur):

        valeurs = []

        if pred_lineaire is not None:

            valeur = pred_lineaire[i]

            if pd.notna(valeur):
                valeurs.append(float(valeur))

        valeur_j = pred_journaliere[i]

        if pd.notna(valeur_j):
            valeurs.append(float(valeur_j))

        if len(valeurs) == 0:
            predictions.append(np.nan)

        else:
            predictions.append(
                float(np.mean(valeurs))
            )

    return predictions


# =============================================================================
# CHOIX DE LA METHODE
# =============================================================================

def choisir_methode(longueur):
    """
    Choix issu directement du benchmark temporel.

    1 point  -> linéaire
    2 points -> hybride
    3 points -> hybride
    8 points -> journalière +/- 24 h
    """

    if longueur == 1:
        return "lineaire"

    if longueur in (2, 3):
        return "hybride"

    if longueur == 8:
        return "journaliere"

    return "non_referencee"


# =============================================================================
# IMPUTATION TEMPORELLE
# =============================================================================

def imputer_temporellement(df):
    """
    Impute les NaN résiduels de la matrice.

    Une copie figée de la matrice d'entrée sert de référence.
    Ainsi, une valeur imputée temporellement n'est jamais
    réutilisée pour calculer une autre imputation.
    """

    reference = df.copy(deep=True)
    resultat = df.copy(deep=True)

    journal = []

    for station in reference.columns:

        serie_reference = reference[station]

        sequences = detecter_sequences_manquantes(
            serie_reference
        )

        for sequence in sequences:

            debut_pos = sequence["debut_pos"]
            fin_pos = sequence["fin_pos"]
            longueur = sequence["longueur"]

            methode = choisir_methode(longueur)

            # ---------------------------------------------------------
            # Calcul des prédictions
            # ---------------------------------------------------------

            if methode == "lineaire":

                predictions = prediction_lineaire(
                    serie_reference,
                    debut_pos,
                    fin_pos
                )

                if predictions is None:
                    predictions = [
                        np.nan
                    ] * longueur

            elif methode == "hybride":

                predictions = prediction_hybride(
                    serie_reference,
                    debut_pos,
                    fin_pos
                )

            elif methode == "journaliere":

                predictions = prediction_journaliere(
                    serie_reference,
                    debut_pos,
                    fin_pos
                )

            else:

                predictions = [
                    np.nan
                ] * longueur

            # ---------------------------------------------------------
            # Enregistrement
            # ---------------------------------------------------------

            for j, pos in enumerate(
                range(debut_pos, fin_pos + 1)
            ):

                timestamp = reference.index[pos]

                prediction = predictions[j]

                valeur_avant = np.nan
                valeur_apres = np.nan
                valeur_moins_24h = np.nan
                valeur_plus_24h = np.nan

                # Valeur immédiatement avant
                if debut_pos > 0:
                    valeur_avant = (
                        serie_reference.iloc[
                            debut_pos - 1
                        ]
                    )

                # Valeur immédiatement après
                if fin_pos < len(
                    serie_reference
                ) - 1:
                    valeur_apres = (
                        serie_reference.iloc[
                            fin_pos + 1
                        ]
                    )

                # Valeurs +/- 24 h
                t_moins_24 = (
                    timestamp
                    - pd.Timedelta(hours=24)
                )

                t_plus_24 = (
                    timestamp
                    + pd.Timedelta(hours=24)
                )

                if t_moins_24 in serie_reference.index:
                    valeur_moins_24h = (
                        serie_reference.loc[
                            t_moins_24
                        ]
                    )

                if t_plus_24 in serie_reference.index:
                    valeur_plus_24h = (
                        serie_reference.loc[
                            t_plus_24
                        ]
                    )

                # On ne modifie que les NaN.
                if pd.notna(prediction):

                    resultat.iat[
                        pos,
                        resultat.columns.get_loc(
                            station
                        )
                    ] = prediction

                journal.append(
                    {
                        "timestamp": timestamp,
                        "station": station,
                        "longueur_sequence":
                            longueur,
                        "duree_heures":
                            longueur * 3,
                        "position_dans_sequence":
                            j + 1,
                        "methode": methode,
                        "temperature_imputee":
                            prediction,
                        "valeur_avant":
                            valeur_avant,
                        "valeur_apres":
                            valeur_apres,
                        "valeur_moins_24h":
                            valeur_moins_24h,
                        "valeur_plus_24h":
                            valeur_plus_24h,
                        "imputation_reussie":
                            pd.notna(prediction),
                    }
                )

    journal = pd.DataFrame(journal)

    return resultat, journal


# =============================================================================
# CONTROLES
# =============================================================================

def controler_resultats(
    original,
    final,
    journal
):
    """
    Vérifie que l'imputation n'a pas modifié les valeurs
    déjà présentes avant l'étape temporelle.
    """

    titre("CONTROLES DE COHERENCE")

    masque_observe = original.notna()

    valeurs_avant = original.where(
        masque_observe
    )

    valeurs_apres = final.where(
        masque_observe
    )

    # Comparaison avec tolérance numérique.
    avant = valeurs_avant.to_numpy(
        dtype=float
    )

    apres = valeurs_apres.to_numpy(
        dtype=float
    )

    masque = ~np.isnan(avant)

    valeurs_modifiees = np.sum(
        ~np.isclose(
            avant[masque],
            apres[masque],
            equal_nan=True
        )
    )

    nan_avant = int(
        original.isna().sum().sum()
    )

    nan_apres = int(
        final.isna().sum().sum()
    )

    imputations_reussies = int(
        journal["imputation_reussie"].sum()
    )

    print(
        "Valeurs manquantes avant :",
        nan_avant
    )

    print(
        "Imputations temporelles réussies :",
        imputations_reussies
    )

    print(
        "Valeurs manquantes après :",
        nan_apres
    )

    print(
        "Valeurs déjà présentes modifiées :",
        int(valeurs_modifiees)
    )

    if valeurs_modifiees != 0:
        raise AssertionError(
            "Des valeurs déjà présentes ont été modifiées."
        )

    if (
        nan_avant
        != imputations_reussies + nan_apres
    ):
        raise AssertionError(
            "Incohérence dans le nombre "
            "d'imputations."
        )

    print("\nContrôles : OK")


# =============================================================================
# RESUME
# =============================================================================

def afficher_resume(
    original,
    final,
    journal
):
    """
    Affiche le bilan final.
    """

    titre("BILAN DE L'IMPUTATION TEMPORELLE")

    n_avant = int(
        original.isna().sum().sum()
    )

    n_apres = int(
        final.isna().sum().sum()
    )

    n_imputees = n_avant - n_apres

    couverture = (
        100 * n_imputees / n_avant
        if n_avant > 0
        else 100.0
    )

    print(
        "Valeurs manquantes initiales :",
        n_avant
    )

    print(
        "Valeurs imputées temporellement :",
        n_imputees
    )

    print(
        "Valeurs restant manquantes :",
        n_apres
    )

    print(
        "Couverture temporelle :",
        f"{couverture:.3f} %"
    )

    titre("REPARTITION PAR METHODE")

    resume_methodes = (
        journal
        .groupby("methode")
        .agg(
            nombre_valeurs=(
                "timestamp",
                "size"
            ),
            imputations_reussies=(
                "imputation_reussie",
                "sum"
            )
        )
        .reset_index()
    )

    resume_methodes[
        "couverture_pct"
    ] = (
        100
        * resume_methodes[
            "imputations_reussies"
        ]
        / resume_methodes[
            "nombre_valeurs"
        ]
    )

    print(
        resume_methodes.to_string(
            index=False,
            formatters={
                "couverture_pct":
                    "{:.3f}".format
            }
        )
    )

    titre("REPARTITION PAR LONGUEUR")

    resume_longueurs = (
        journal
        .groupby(
            [
                "longueur_sequence",
                "duree_heures",
                "methode"
            ]
        )
        .agg(
            nombre_valeurs=(
                "timestamp",
                "size"
            ),
            imputations_reussies=(
                "imputation_reussie",
                "sum"
            )
        )
        .reset_index()
    )

    resume_longueurs[
        "couverture_pct"
    ] = (
        100
        * resume_longueurs[
            "imputations_reussies"
        ]
        / resume_longueurs[
            "nombre_valeurs"
        ]
    )

    print(
        resume_longueurs.to_string(
            index=False,
            formatters={
                "couverture_pct":
                    "{:.3f}".format
            }
        )
    )

    titre("20 EXEMPLES D'IMPUTATIONS TEMPORELLES")

    exemples = journal[
        journal["imputation_reussie"]
    ].head(20)

    colonnes = [
        "timestamp",
        "station",
        "longueur_sequence",
        "duree_heures",
        "position_dans_sequence",
        "methode",
        "temperature_imputee",
    ]

    print(
        exemples[colonnes].to_string(
            index=False
        )
    )

    if n_apres > 0:

        titre("VALEURS ENCORE MANQUANTES")

        masque = final.isna()

        lignes = []

        for station in final.columns:

            dates = final.index[
                masque[station]
            ]

            for timestamp in dates:

                lignes.append(
                    {
                        "timestamp":
                            timestamp,
                        "station":
                            station
                    }
                )

        restants = pd.DataFrame(
            lignes
        )

        print(
            "Nombre :",
            len(restants)
        )

        print(
            "\nRépartition par station :"
        )

        print(
            restants[
                "station"
            ].value_counts().head(20)
        )

        print(
            "\nRépartition par timestamp :"
        )

        print(
            restants[
                "timestamp"
            ].value_counts().head(20)
        )

    else:

        titre("MATRICE COMPLETE")

        print(
            "Toutes les températures "
            "manquantes ont été imputées."
        )

        print(
            "Nombre final de NaN : 0"
        )


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sauvegarder(
    final,
    journal
):
    """
    Sauvegarde la matrice finale et le journal.
    """

    DOSSIER_METEO.mkdir(
        parents=True,
        exist_ok=True
    )

    final.to_csv(
        FICHIER_SORTIE,
        index=True,
        index_label="timestamp"
    )

    journal.to_csv(
        FICHIER_JOURNAL,
        index=False
    )

    titre("FICHIERS CREES")

    print(
        "Matrice finale :",
        FICHIER_SORTIE
    )

    print(
        "Journal temporel :",
        FICHIER_JOURNAL
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    titre(
        "IMPUTATION TEMPORELLE FINALE "
        "DES TEMPERATURES SYNOP"
    )

    print(
        "\nLecture de la matrice "
        "après imputation spatiale..."
    )

    original = lire_matrice()

    print(
        "\nDimensions :",
        original.shape
    )

    print(
        "Première date :",
        original.index.min()
    )

    print(
        "Dernière date :",
        original.index.max()
    )

    n_manquantes = int(
        original.isna().sum().sum()
    )

    print(
        "Valeurs manquantes avant "
        "imputation temporelle :",
        n_manquantes
    )

    # -------------------------------------------------------------
    # Contrôle attendu
    # -------------------------------------------------------------

    if n_manquantes != 1492:

        print(
            "\nATTENTION : le nombre de NaN "
            "n'est pas égal aux 1492 valeurs "
            "attendues d'après le diagnostic."
        )

        print(
            "Le script continue néanmoins "
            "avec les données présentes."
        )

    # -------------------------------------------------------------
    # Imputation
    # -------------------------------------------------------------

    titre(
        "IMPUTATION DES TROUS RESIDUELS"
    )

    final, journal = (
        imputer_temporellement(
            original
        )
    )

    # -------------------------------------------------------------
    # Contrôles
    # -------------------------------------------------------------

    controler_resultats(
        original,
        final,
        journal
    )

    # -------------------------------------------------------------
    # Résumé
    # -------------------------------------------------------------

    afficher_resume(
        original,
        final,
        journal
    )

    # -------------------------------------------------------------
    # Sauvegarde
    # -------------------------------------------------------------

    sauvegarder(
        final,
        journal
    )

    titre(
        "IMPUTATION TEMPORELLE TERMINEE"
    )

    print(
        "La matrice issue de l'imputation "
        "spatiale n'a pas été écrasée."
    )

    print(
        "La matrice finale est enregistrée "
        "dans un nouveau fichier."
    )


if __name__ == "__main__":
    main()