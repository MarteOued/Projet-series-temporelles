"""
Imputation temporelle finale des températures SYNOP.

Ce script intervient APRES l'imputation spatiale. Il traite les valeurs qui
restent manquantes, surtout des pannes de tout le réseau (aucune station
voisine disponible au même instant).

Règle : l'imputation est CAUSALE. Une valeur manquante à l'instant t n'est
reconstruite qu'avec des observations antérieures au trou. Aucune méthode
n'utilise l'observation suivante ni le lendemain : sinon, une prévision faite
à 14 h pourrait s'appuyer sur une température qui n'existait pas encore.

Méthodes : persistance, veille, persistance ajustée (voir plus bas). La méthode
de chaque longueur de trou est choisie par le benchmark temporel, calculé sur
la période d'apprentissage uniquement, et la règle fonctionne pour une
longueur de trou quelconque.

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
from src import config


# =============================================================================
# CONFIGURATION
# =============================================================================


DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

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
# METHODES CAUSALES
# =============================================================================
#
# Règle commune : pour imputer la valeur à la position `pos`, on n'utilise que
# des observations situées AVANT le trou (positions < debut_pos). Aucune méthode
# ne regarde l'observation suivante ni le lendemain : une valeur imputée à
# l'instant t ne dépend que de ce qui était connu à l'instant t.
#
# Les fonctions reçoivent un tableau numpy (la série d'une station, après
# imputation spatiale) et renvoient une liste de prédictions (NaN si la méthode
# ne peut pas calculer un point).

PAS_HEURES = config.PAS_SYNOP_HEURES
DECALAGE_24H = 24 // PAS_HEURES           # 8 positions = 24 heures
NB_JOURS_RECUL_MAX = 7                    # on remonte au plus 7 jours en arrière

METHODES_CAUSALES = ["persistance", "veille", "persistance_ajustee"]


def _valeur(serie, position):
    """Valeur à une position, ou NaN si la position sort de la série."""
    if 0 <= position < len(serie):
        return float(serie[position])
    return np.nan


def prediction_persistance(serie, debut_pos, fin_pos):
    """Dernière valeur observée avant le trou, recopiée sur tout le trou."""
    derniere = _valeur(serie, debut_pos - 1)
    return [derniere] * (fin_pos - debut_pos + 1)


def prediction_veille(serie, debut_pos, fin_pos):
    """Même heure la veille (ou 2, 3... jours avant si la veille manque aussi).

    Seules les positions antérieures au début du trou sont utilisées.
    """
    predictions = []
    for pos in range(debut_pos, fin_pos + 1):
        valeur = np.nan
        for jours in range(1, NB_JOURS_RECUL_MAX + 1):
            position = pos - jours * DECALAGE_24H
            if position < debut_pos:
                valeur = _valeur(serie, position)
                if not np.isnan(valeur):
                    break
        predictions.append(valeur)
    return predictions


def prediction_persistance_ajustee(serie, debut_pos, fin_pos):
    """Dernière valeur observée + évolution de la veille sur les mêmes heures.

    T(t) ≈ T(dernière obs) + [T(t − 24 h) − T(dernière obs − 24 h)].
    Le niveau vient de la dernière observation, la forme de la journée (cycle
    jour/nuit) vient de la veille. Si la veille manque, on recule de 24 h de plus.
    """
    derniere_pos = debut_pos - 1
    derniere = _valeur(serie, derniere_pos)
    predictions = []
    for pos in range(debut_pos, fin_pos + 1):
        valeur = np.nan
        if not np.isnan(derniere):
            for jours in range(1, NB_JOURS_RECUL_MAX + 1):
                recul = jours * DECALAGE_24H
                if pos - recul >= debut_pos:
                    continue  # ce point de la veille est encore dans le trou
                avant = _valeur(serie, pos - recul)
                reference = _valeur(serie, derniere_pos - recul)
                if not (np.isnan(avant) or np.isnan(reference)):
                    valeur = derniere + (avant - reference)
                    break
        predictions.append(valeur)
    return predictions


FONCTIONS_METHODES = {
    "persistance": prediction_persistance,
    "veille": prediction_veille,
    "persistance_ajustee": prediction_persistance_ajustee,
}


# =============================================================================
# CHOIX DE LA METHODE
# =============================================================================

FICHIER_CHOIX = DOSSIER_METEO / "benchmark_imputation_temporelle.csv"


def lire_choix_methodes(chemin=None):
    """Meilleure méthode causale pour chaque longueur testée par le benchmark.

    Le benchmark (src/benchmark_imputation_temporelle.py) est calculé sur la
    période d'apprentissage uniquement. Renvoie un dict {longueur: méthode}.
    """
    chemin = FICHIER_CHOIX if chemin is None else chemin
    if not chemin.exists():
        raise FileNotFoundError(
            f"Résultats du benchmark temporel introuvables : {chemin}. "
            "Lancer d'abord python -m src.benchmark_imputation_temporelle."
        )
    resultats = pd.read_csv(chemin)
    causales = resultats[resultats["methode"].isin(METHODES_CAUSALES)]
    meilleures = causales.loc[causales.groupby("longueur_points")["MAE"].idxmin()]
    return dict(zip(meilleures["longueur_points"].astype(int), meilleures["methode"]))


def choisir_methode(longueur, choix):
    """Méthode à utiliser pour un trou de `longueur` points, quelle que soit sa longueur.

    On prend le choix du benchmark pour la plus grande longueur testée qui ne
    dépasse pas `longueur` (ou la plus petite longueur testée si le trou est
    plus court que toutes).
    """
    longueurs = sorted(choix)
    candidates = [l for l in longueurs if l <= longueur]
    reference = candidates[-1] if candidates else longueurs[0]
    return choix[reference]


# =============================================================================
# IMPUTATION TEMPORELLE
# =============================================================================

def imputer_temporellement(df, choix):
    """Impute les NaN résiduels de la matrice avec une méthode causale.

    Une copie figée de la matrice d'entrée sert de référence : une valeur
    imputée temporellement n'est jamais réutilisée pour en calculer une autre.
    Si la méthode choisie ne peut pas calculer un point (données d'avant
    absentes), on essaie les autres méthodes causales dans l'ordre :
    persistance ajustée, veille, persistance.
    """

    reference = df.copy(deep=True)
    resultat = df.copy(deep=True)

    journal = []

    for station in reference.columns:

        serie = reference[station].to_numpy(dtype=float)

        for sequence in detecter_sequences_manquantes(reference[station]):

            debut_pos = sequence["debut_pos"]
            fin_pos = sequence["fin_pos"]
            longueur = sequence["longueur"]

            methode_choisie = choisir_methode(longueur, choix)
            ordre = [methode_choisie] + [
                m for m in ["persistance_ajustee", "veille", "persistance"]
                if m != methode_choisie
            ]
            predictions_par_methode = {
                m: FONCTIONS_METHODES[m](serie, debut_pos, fin_pos) for m in ordre
            }

            for j, pos in enumerate(range(debut_pos, fin_pos + 1)):

                prediction = np.nan
                methode_utilisee = ""
                for m in ordre:
                    if not np.isnan(predictions_par_methode[m][j]):
                        prediction = predictions_par_methode[m][j]
                        methode_utilisee = m
                        break

                if not np.isnan(prediction):
                    resultat.iat[pos, resultat.columns.get_loc(station)] = prediction

                journal.append(
                    {
                        "timestamp": reference.index[pos],
                        "station": station,
                        "longueur_sequence": longueur,
                        "duree_heures": longueur * PAS_HEURES,
                        "position_dans_sequence": j + 1,
                        "methode": methode_utilisee or methode_choisie,
                        "methode_choisie": methode_choisie,
                        "temperature_imputee": prediction,
                        "valeur_avant": _valeur(serie, debut_pos - 1),
                        "valeur_moins_24h": _valeur(serie, pos - DECALAGE_24H),
                        "imputation_reussie": not np.isnan(prediction),
                    }
                )

    return resultat, pd.DataFrame(journal)


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

    choix = lire_choix_methodes()

    print("\nMéthode retenue par longueur de trou (benchmark sur l'apprentissage) :")
    for longueur, methode in sorted(choix.items()):
        print(f"  {longueur} point(s) = {longueur * PAS_HEURES} h : {methode}")

    # -------------------------------------------------------------
    # Imputation
    # -------------------------------------------------------------

    titre(
        "IMPUTATION DES TROUS RESIDUELS"
    )

    final, journal = (
        imputer_temporellement(
            original,
            choix,
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