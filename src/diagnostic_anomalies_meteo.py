"""
Diagnostic final des anomalies de température SYNOP.

Objectifs
---------
1. Analyser la matrice finale APRES correction des anomalies.
2. Détecter les variations de température > 15 °C en 3 heures.
3. Identifier l'origine des valeurs :
   - observation originale ;
   - imputation spatiale ;
   - imputation temporelle ;
   - correction_anomalie.
4. Vérifier spécifiquement les anomalies corrigées
   (liste lue dans le journal des corrections : elle n'est plus écrite à la main)
5. Contrôler qu'aucune nouvelle anomalie n'a été créée.

IMPORTANT
---------
Ce script est uniquement diagnostique.
Il ne modifie aucune température.

Exécution
---------
python -m src.diagnostic_anomalies_meteo
"""

from pathlib import Path

import numpy as np
import pandas as pd
from src import config


# =============================================================================
# CONFIGURATION
# =============================================================================


DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

FICHIER_ORIGINAL = (
    DOSSIER_METEO
    / "temperatures_synop_originales.csv"
)

FICHIER_SPATIAL = (
    DOSSIER_METEO
    / "temperatures_synop_imputees.csv"
)

FICHIER_COMPLET_AVANT_CORRECTION = (
    DOSSIER_METEO
    / "temperatures_synop_completes.csv"
)

# IMPORTANT :
# matrice finale APRES correction des anomalies
FICHIER_FINAL = (
    DOSSIER_METEO
    / "temperatures_synop_finales.csv"
)

FICHIER_JOURNAL_SPATIAL = (
    DOSSIER_METEO
    / "journal_imputation_synop.csv"
)

FICHIER_JOURNAL_TEMPOREL = (
    DOSSIER_METEO
    / "journal_imputation_temporelle.csv"
)

FICHIER_JOURNAL_CORRECTIONS = (
    DOSSIER_METEO
    / "journal_correction_anomalies.csv"
)

# On crée de nouveaux diagnostics pour ne pas écraser
# ceux obtenus avant correction.
FICHIER_SORTIE = (
    DOSSIER_METEO
    / "diagnostic_anomalies_temperatures_final.csv"
)

FICHIER_CONTEXTE = (
    DOSSIER_METEO
    / "contexte_anomalies_temperatures_final.csv"
)

FICHIER_CONTROLE_SPATIAL = (
    DOSSIER_METEO
    / "controle_spatial_anomalies_final.csv"
)


SEUIL_VARIATION = 15.0

NB_PAS_CONTEXTE = 2

NB_VOISINS = 5


# Observations corrigées par src/correction_anomalies_meteo.py. Elles ne sont
# plus écrites à la main : la liste est remplie au lancement à partir du
# journal des corrections (voir main).
CAS_CORRIGES = []


def cas_depuis_journal(journal_corrections):
    """Liste des cas corrigés, au format attendu par les fonctions de ce module."""
    if journal_corrections.empty:
        return []
    return [
        {
            "station": ligne.station,
            "nom": getattr(ligne, "nom_station", ""),
            "timestamp": str(ligne.timestamp),
            "ancienne_valeur": float(ligne.valeur_originale),
        }
        for ligne in journal_corrections.itertuples(index=False)
    ]


# =============================================================================
# OUTILS
# =============================================================================

def titre(texte):
    print()
    print("=" * 90)
    print(texte)
    print("=" * 90)


def charger_matrice(chemin):
    """
    Charge une matrice de températures avec timestamp en index.
    """

    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {chemin}"
        )

    df = pd.read_csv(
        chemin,
        index_col=0,
        parse_dates=True,
    )

    df.index = pd.to_datetime(
        df.index,
        utc=True,
        errors="raise",
    )

    df.index.name = "timestamp"

    df.columns = [
        str(col).zfill(5)
        for col in df.columns
    ]

    df = df.apply(
        pd.to_numeric,
        errors="coerce",
    )

    return df


def charger_journal(chemin):
    """
    Charge un journal s'il existe.
    """

    if not chemin.exists():
        return pd.DataFrame()

    journal = pd.read_csv(chemin)

    if "timestamp" in journal.columns:
        journal["timestamp"] = pd.to_datetime(
            journal["timestamp"],
            utc=True,
            errors="coerce",
        )

    if "station" in journal.columns:
        journal["station"] = (
            journal["station"]
            .astype(str)
            .str.zfill(5)
        )

    return journal


# =============================================================================
# IDENTIFICATION DES CORRECTIONS
# =============================================================================

def construire_positions_corrigees(journal_corrections):
    """
    Construit l'ensemble des couples
    (timestamp, station) corrigés manuellement.
    """

    positions = set()

    if journal_corrections.empty:
        return positions

    if not {
        "timestamp",
        "station",
    }.issubset(journal_corrections.columns):
        return positions

    for _, ligne in journal_corrections.iterrows():

        timestamp = ligne["timestamp"]
        station = ligne["station"]

        if pd.isna(timestamp):
            continue

        positions.add(
            (
                pd.Timestamp(timestamp),
                str(station).zfill(5),
            )
        )

    return positions


# =============================================================================
# ORIGINE DES VALEURS
# =============================================================================

def origine_valeur(
    timestamp,
    station,
    original,
    spatial,
    complet_avant_correction,
    final,
    positions_corrigees,
):
    """
    Détermine l'origine de la valeur utilisée dans la matrice finale.
    """

    if (
        timestamp,
        station,
    ) in positions_corrigees:
        return "correction_anomalie"

    valeur_originale = original.at[
        timestamp,
        station,
    ]

    valeur_spatiale = spatial.at[
        timestamp,
        station,
    ]

    valeur_complete = complet_avant_correction.at[
        timestamp,
        station,
    ]

    valeur_finale = final.at[
        timestamp,
        station,
    ]

    if pd.notna(valeur_originale):
        return "observee"

    if pd.notna(valeur_spatiale):
        return "imputation_spatiale"

    if pd.notna(valeur_complete):
        return "imputation_temporelle"

    if pd.notna(valeur_finale):
        return "valeur_finale"

    return "inconnue"


# =============================================================================
# DETECTION DES VARIATIONS
# =============================================================================

def detecter_variations(final):
    """
    Détecte les variations absolues supérieures au seuil.
    """

    delta = final.diff()

    masque = delta.abs() > SEUIL_VARIATION

    positions = np.where(
        masque.to_numpy()
    )

    lignes = []

    for i, j in zip(
        positions[0],
        positions[1],
    ):

        if i == 0:
            continue

        timestamp = final.index[i]
        timestamp_precedent = final.index[i - 1]
        station = final.columns[j]

        temperature_precedente = final.iloc[
            i - 1,
            j,
        ]

        temperature = final.iloc[
            i,
            j,
        ]

        variation = (
            temperature
            - temperature_precedente
        )

        lignes.append(
            {
                "timestamp_precedent":
                    timestamp_precedent,
                "timestamp":
                    timestamp,
                "station":
                    station,
                "temperature_precedente":
                    temperature_precedente,
                "temperature":
                    temperature,
                "variation":
                    variation,
                "variation_absolue":
                    abs(variation),
            }
        )

    anomalies = pd.DataFrame(lignes)

    if not anomalies.empty:

        anomalies = (
            anomalies
            .sort_values(
                "variation_absolue",
                ascending=False,
            )
            .reset_index(drop=True)
        )

    return anomalies


# =============================================================================
# AJOUT DES ORIGINES
# =============================================================================

def ajouter_origines(
    anomalies,
    original,
    spatial,
    complet_avant_correction,
    final,
    positions_corrigees,
):
    """
    Ajoute l'origine des valeurs constituant chaque variation.
    """

    if anomalies.empty:
        return anomalies

    origine_precedente = []
    origine_actuelle = []

    for _, ligne in anomalies.iterrows():

        station = ligne["station"]

        timestamp_precedent = (
            ligne["timestamp_precedent"]
        )

        timestamp = ligne["timestamp"]

        origine_precedente.append(
            origine_valeur(
                timestamp_precedent,
                station,
                original,
                spatial,
                complet_avant_correction,
                final,
                positions_corrigees,
            )
        )

        origine_actuelle.append(
            origine_valeur(
                timestamp,
                station,
                original,
                spatial,
                complet_avant_correction,
                final,
                positions_corrigees,
            )
        )

    anomalies = anomalies.copy()

    anomalies[
        "origine_temperature_precedente"
    ] = origine_precedente

    anomalies[
        "origine_temperature"
    ] = origine_actuelle

    return anomalies


# =============================================================================
# CONTEXTE TEMPOREL
# =============================================================================

def construire_contexte(
    anomalies,
    final,
    original,
):
    """
    Construit le contexte temporel autour de chaque anomalie.
    """

    lignes = []

    for numero, anomalie in anomalies.iterrows():

        timestamp = anomalie["timestamp"]
        station = anomalie["station"]

        position = final.index.get_loc(
            timestamp
        )

        debut = max(
            0,
            position - NB_PAS_CONTEXTE - 1,
        )

        fin = min(
            len(final),
            position + NB_PAS_CONTEXTE + 1,
        )

        for i in range(debut, fin):

            ts = final.index[i]

            temperature_finale = final.at[
                ts,
                station,
            ]

            temperature_originale = original.at[
                ts,
                station,
            ]

            lignes.append(
                {
                    "numero_anomalie":
                        numero + 1,
                    "station":
                        station,
                    "timestamp_anomalie":
                        timestamp,
                    "timestamp":
                        ts,
                    "decalage_heures":
                        int(
                            (
                                ts - timestamp
                            ).total_seconds()
                            / 3600
                        ),
                    "temperature_finale":
                        temperature_finale,
                    "temperature_originale":
                        temperature_originale,
                    "est_originale":
                        pd.notna(
                            temperature_originale
                        ),
                }
            )

    return pd.DataFrame(lignes)


# =============================================================================
# CORRELATIONS
# =============================================================================

def calculer_correlations(original):
    """
    Calcule les corrélations entre stations à partir
    des observations originales.
    """

    return original.corr(
        min_periods=100
    )


def meilleurs_voisins(
    station,
    correlations,
    n=5,
):
    """
    Retourne les n stations les plus corrélées.
    """

    if station not in correlations.columns:
        return pd.Series(dtype=float)

    serie = (
        correlations[station]
        .drop(
            labels=[station],
            errors="ignore",
        )
        .dropna()
        .sort_values(
            ascending=False
        )
    )

    return serie.head(n)


# =============================================================================
# VERIFICATION DES CORRECTIONS
# =============================================================================

def verifier_corrections(
    complet_avant_correction,
    final,
    correlations,
):
    """
    Vérifie spécifiquement les deux valeurs corrigées.
    """

    titre(
        "VERIFICATION DES ANOMALIES CORRIGEES"
    )

    resultats = []

    for cas in CAS_CORRIGES:

        station = cas["station"]
        nom = cas["nom"]
        timestamp = pd.Timestamp(
            cas["timestamp"]
        )

        ancienne_valeur = cas[
            "ancienne_valeur"
        ]

        valeur_avant = (
            complet_avant_correction.at[
                timestamp,
                station,
            ]
        )

        valeur_apres = final.at[
            timestamp,
            station,
        ]

        voisins = meilleurs_voisins(
            station,
            correlations,
            n=NB_VOISINS,
        )

        valeurs_voisins = []

        for voisin in voisins.index:

            valeur = final.at[
                timestamp,
                voisin,
            ]

            if pd.notna(valeur):
                valeurs_voisins.append(
                    valeur
                )

        print()
        print("-" * 90)
        print(
            f"{station} - {nom}"
        )
        print(
            "Timestamp :",
            timestamp,
        )
        print(
            f"Valeur avant correction : "
            f"{valeur_avant:.3f} °C"
        )
        print(
            f"Valeur corrigée : "
            f"{valeur_apres:.3f} °C"
        )

        correction_effective = (
            not np.isclose(
                valeur_avant,
                valeur_apres,
            )
        )

        print(
            "Correction effective :",
            "OUI"
            if correction_effective
            else "NON",
        )

        if valeurs_voisins:

            moyenne = float(
                np.mean(valeurs_voisins)
            )

            mediane = float(
                np.median(valeurs_voisins)
            )

            print(
                f"Moyenne des {len(valeurs_voisins)} "
                f"voisins : {moyenne:.3f} °C"
            )

            print(
                f"Médiane des voisins : "
                f"{mediane:.3f} °C"
            )

            print(
                "Écart corrigée - moyenne : "
                f"{valeur_apres - moyenne:+.3f} °C"
            )

        else:

            moyenne = np.nan
            mediane = np.nan

        resultats.append(
            {
                "timestamp":
                    timestamp,
                "station":
                    station,
                "nom_station":
                    nom,
                "ancienne_valeur_attendue":
                    ancienne_valeur,
                "valeur_avant_correction":
                    valeur_avant,
                "valeur_apres_correction":
                    valeur_apres,
                "correction_effective":
                    correction_effective,
                "moyenne_voisins":
                    moyenne,
                "mediane_voisins":
                    mediane,
            }
        )

    return pd.DataFrame(resultats)


# =============================================================================
# CONTROLE SPATIAL DES CORRECTIONS
# =============================================================================

def controle_spatial_cas_corriges(
    final,
    correlations,
):
    """
    Compare les deux valeurs corrigées à leurs voisins.
    """

    titre(
        "CONTROLE SPATIAL DES VALEURS CORRIGEES"
    )

    resultats = []

    for cas in CAS_CORRIGES:

        station = cas["station"]
        nom = cas["nom"]
        timestamp = pd.Timestamp(
            cas["timestamp"]
        )

        valeur_corrigee = final.at[
            timestamp,
            station,
        ]

        voisins = meilleurs_voisins(
            station,
            correlations,
            n=NB_VOISINS,
        )

        print()
        print("-" * 90)
        print(
            f"{station} - {nom}"
        )
        print(
            "Timestamp :",
            timestamp,
        )
        print(
            f"Température corrigée : "
            f"{valeur_corrigee:.3f} °C"
        )

        print()
        print(
            f"{len(voisins)} voisins "
            "les plus corrélés :"
        )

        valeurs_voisins = []

        for rang, (
            voisin,
            correlation,
        ) in enumerate(
            voisins.items(),
            start=1,
        ):

            temperature = final.at[
                timestamp,
                voisin,
            ]

            print(
                f"{rang}. {voisin} "
                f"| r = {correlation:.4f} "
                f"| T = {temperature:.3f} °C"
            )

            if pd.notna(temperature):
                valeurs_voisins.append(
                    temperature
                )

            resultats.append(
                {
                    "station_corrigee":
                        station,
                    "nom_station":
                        nom,
                    "timestamp":
                        timestamp,
                    "temperature_corrigee":
                        valeur_corrigee,
                    "station_voisine":
                        voisin,
                    "rang_voisin":
                        rang,
                    "correlation":
                        correlation,
                    "temperature_voisine":
                        temperature,
                }
            )

        if valeurs_voisins:

            valeurs_voisins = np.array(
                valeurs_voisins,
                dtype=float,
            )

            moyenne = np.mean(
                valeurs_voisins
            )

            mediane = np.median(
                valeurs_voisins
            )

            print()
            print(
                "Résumé des voisins"
            )

            print(
                f"Moyenne : "
                f"{moyenne:.3f} °C"
            )

            print(
                f"Médiane : "
                f"{mediane:.3f} °C"
            )

            print(
                "Écart valeur corrigée - moyenne : "
                f"{valeur_corrigee - moyenne:+.3f} °C"
            )

            print(
                "Écart valeur corrigée - médiane : "
                f"{valeur_corrigee - mediane:+.3f} °C"
            )

    return pd.DataFrame(
        resultats
    )


# =============================================================================
# CONTEXTE SPATIO-TEMPOREL DES CORRECTIONS
# =============================================================================

def afficher_contexte_corrections(
    final,
    correlations,
):
    """
    Affiche le contexte temporel des deux valeurs corrigées.
    """

    titre(
        "CONTEXTE SPATIO-TEMPOREL "
        "DES VALEURS CORRIGEES"
    )

    for cas in CAS_CORRIGES:

        station = cas["station"]
        nom = cas["nom"]

        timestamp = pd.Timestamp(
            cas["timestamp"]
        )

        voisins = list(
            meilleurs_voisins(
                station,
                correlations,
                n=3,
            ).index
        )

        stations_affichees = [
            station,
            *voisins,
        ]

        position = final.index.get_loc(
            timestamp
        )

        debut = max(
            0,
            position - 2,
        )

        fin = min(
            len(final),
            position + 3,
        )

        timestamps = final.index[
            debut:fin
        ]

        tableau = final.loc[
            timestamps,
            stations_affichees,
        ].copy()

        print()
        print("-" * 90)
        print(
            f"{station} - {nom}"
        )

        print(
            "Station corrigée + "
            "3 meilleurs voisins"
        )

        print()
        print(
            tableau.to_string()
        )


# =============================================================================
# RESUME
# =============================================================================

def afficher_resume(anomalies):

    titre(
        "RESUME FINAL DES ANOMALIES"
    )

    print(
        f"Seuil : "
        f"{SEUIL_VARIATION} °C en 3 h"
    )

    print(
        "Nombre de variations détectées :",
        len(anomalies),
    )

    if anomalies.empty:
        return

    print()
    print(
        "Origine des valeurs ACTUELLES :"
    )

    print(
        anomalies[
            "origine_temperature"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "Origine des valeurs PRECEDENTES :"
    )

    print(
        anomalies[
            "origine_temperature_precedente"
        ]
        .value_counts()
        .to_string()
    )


def afficher_anomalies(anomalies):

    titre(
        "DETAIL DES VARIATIONS "
        "ANORMALES RESTANTES"
    )

    if anomalies.empty:

        print(
            "Aucune variation supérieure "
            "au seuil."
        )

        return

    colonnes = [
        "timestamp",
        "station",
        "temperature_precedente",
        "temperature",
        "variation",
        "origine_temperature_precedente",
        "origine_temperature",
    ]

    print(
        anomalies[
            colonnes
        ].to_string(
            index=False
        )
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    titre(
        "DIAGNOSTIC FINAL DES ANOMALIES "
        "DE TEMPERATURE SYNOP"
    )

    print()
    print(
        "Lecture des matrices..."
    )

    original = charger_matrice(
        FICHIER_ORIGINAL
    )

    spatial = charger_matrice(
        FICHIER_SPATIAL
    )

    complet_avant_correction = charger_matrice(
        FICHIER_COMPLET_AVANT_CORRECTION
    )

    final = charger_matrice(
        FICHIER_FINAL
    )

    print(
        "Dimensions :",
        final.shape,
    )

    print(
        "Première date :",
        final.index.min(),
    )

    print(
        "Dernière date :",
        final.index.max(),
    )

    print(
        "Valeurs manquantes :",
        int(final.isna().sum().sum()),
    )

    # =========================================================================
    # CONTROLES DES MATRICES
    # =========================================================================

    titre(
        "CONTROLES DE COHERENCE"
    )

    matrices = [
        original,
        spatial,
        complet_avant_correction,
        final,
    ]

    if not all(
        matrice.shape == final.shape
        for matrice in matrices
    ):
        raise ValueError(
            "Les matrices n'ont pas "
            "les mêmes dimensions."
        )

    if not all(
        matrice.index.equals(final.index)
        for matrice in matrices
    ):
        raise ValueError(
            "Les index temporels "
            "ne correspondent pas."
        )

    if not all(
        list(matrice.columns)
        == list(final.columns)
        for matrice in matrices
    ):
        raise ValueError(
            "Les stations ne correspondent pas."
        )

    if final.isna().sum().sum() != 0:
        raise ValueError(
            "La matrice finale contient "
            "encore des valeurs manquantes."
        )

    print(
        "Dimensions : OK"
    )

    print(
        "Index temporels : OK"
    )

    print(
        "Stations : OK"
    )

    print(
        "Valeurs manquantes : 0"
    )

    print(
        "Contrôle matrices : OK"
    )

    # =========================================================================
    # JOURNAUX
    # =========================================================================

    journal_spatial = charger_journal(
        FICHIER_JOURNAL_SPATIAL
    )

    journal_temporel = charger_journal(
        FICHIER_JOURNAL_TEMPOREL
    )

    journal_corrections = charger_journal(
        FICHIER_JOURNAL_CORRECTIONS
    )

    CAS_CORRIGES[:] = cas_depuis_journal(journal_corrections)

    positions_corrigees = (
        construire_positions_corrigees(
            journal_corrections
        )
    )

    print()
    print(
        "Journal spatial :",
        len(journal_spatial),
        "lignes",
    )

    print(
        "Journal temporel :",
        len(journal_temporel),
        "lignes",
    )

    print(
        "Journal corrections :",
        len(journal_corrections),
        "lignes",
    )

    print(
        "Positions corrigées identifiées :",
        len(positions_corrigees),
    )

    # =========================================================================
    # DIFFERENCES AVANT / APRES CORRECTION
    # =========================================================================

    titre(
        "COMPARAISON AVANT / APRES CORRECTION"
    )

    differences = (
        ~np.isclose(
            complet_avant_correction.to_numpy(),
            final.to_numpy(),
            equal_nan=True,
        )
    )

    nombre_modifications = int(
        differences.sum()
    )

    print(
        "Nombre total de valeurs modifiées :",
        nombre_modifications,
    )

    if nombre_modifications != 2:

        print(
            "ATTENTION : on attend exactement "
            "2 valeurs modifiées."
        )

    else:

        print(
            "Contrôle : exactement "
            "2 valeurs ont été modifiées."
        )

    # =========================================================================
    # CORRELATIONS
    # =========================================================================

    titre(
        "CALCUL DES CORRELATIONS"
    )

    correlations = calculer_correlations(
        original
    )

    print(
        "Dimensions de la matrice "
        "de corrélation :",
        correlations.shape,
    )

    print(
        "Calcul des corrélations : OK"
    )

    # =========================================================================
    # VERIFICATION DES CORRECTIONS
    # =========================================================================

    verification = verifier_corrections(
        complet_avant_correction,
        final,
        correlations,
    )

    # =========================================================================
    # DETECTION DES ANOMALIES SUR MATRICE CORRIGEE
    # =========================================================================

    anomalies = detecter_variations(
        final
    )

    anomalies = ajouter_origines(
        anomalies,
        original,
        spatial,
        complet_avant_correction,
        final,
        positions_corrigees,
    )

    afficher_resume(
        anomalies
    )

    afficher_anomalies(
        anomalies
    )

    # =========================================================================
    # CONTEXTE TEMPOREL
    # =========================================================================

    contexte = construire_contexte(
        anomalies,
        final,
        original,
    )

    # =========================================================================
    # CONTROLE SPATIAL
    # =========================================================================

    controle_spatial = (
        controle_spatial_cas_corriges(
            final,
            correlations,
        )
    )

    # =========================================================================
    # CONTEXTE SPATIO-TEMPOREL
    # =========================================================================

    afficher_contexte_corrections(
        final,
        correlations,
    )

    # =========================================================================
    # VERIFICATION QUE LES CORRECTIONS NE SONT PLUS ANORMALES
    # =========================================================================

    titre(
        "CONTROLE FINAL DES CORRECTIONS"
    )

    for cas in CAS_CORRIGES:

        station = cas["station"]

        timestamp = pd.Timestamp(
            cas["timestamp"]
        )

        est_anomalie_actuelle = False
        est_anomalie_precedente = False

        if not anomalies.empty:

            est_anomalie_actuelle = (
                (
                    anomalies["station"]
                    == station
                )
                &
                (
                    anomalies["timestamp"]
                    == timestamp
                )
            ).any()

            est_anomalie_precedente = (
                (
                    anomalies["station"]
                    == station
                )
                &
                (
                    anomalies[
                        "timestamp_precedent"
                    ]
                    == timestamp
                )
            ).any()

        print()
        print(
            f"{station} - {cas['nom']}"
        )

        print(
            "La valeur corrigée produit une "
            "variation > 15 °C avec le point précédent :",
            "OUI"
            if est_anomalie_actuelle
            else "NON",
        )

        print(
            "La valeur corrigée produit une "
            "variation > 15 °C avec le point suivant :",
            "OUI"
            if est_anomalie_precedente
            else "NON",
        )

    # =========================================================================
    # SAUVEGARDE
    # =========================================================================

    titre(
        "SAUVEGARDE DES DIAGNOSTICS FINAUX"
    )

    anomalies.to_csv(
        FICHIER_SORTIE,
        index=False,
    )

    contexte.to_csv(
        FICHIER_CONTEXTE,
        index=False,
    )

    controle_spatial.to_csv(
        FICHIER_CONTROLE_SPATIAL,
        index=False,
    )

    print(
        "Anomalies finales :",
        FICHIER_SORTIE,
    )

    print(
        "Contexte final :",
        FICHIER_CONTEXTE,
    )

    print(
        "Contrôle spatial final :",
        FICHIER_CONTROLE_SPATIAL,
    )

    # =========================================================================
    # CONCLUSION
    # =========================================================================

    titre(
        "BILAN FINAL"
    )

    print(
        "Matrice analysée :",
        FICHIER_FINAL.name,
    )

    print(
        "Nombre de NaN :",
        int(final.isna().sum().sum()),
    )

    print(
        "Nombre de valeurs modifiées "
        "par la correction :",
        nombre_modifications,
    )

    print(
        "Nombre de variations > "
        f"{SEUIL_VARIATION} °C :",
        len(anomalies),
    )

    print()
    print(
        "Aucune température n'a été "
        "modifiée par ce diagnostic."
    )

    print()
    print(
        "Diagnostic final terminé."
    )


if __name__ == "__main__":
    main()