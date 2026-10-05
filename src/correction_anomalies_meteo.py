"""
Correction contrôlée des anomalies météorologiques SYNOP.

Ce script intervient APRES :
    1. l'imputation spatiale ;
    2. l'imputation temporelle.

Principe
--------
Les observations aberrantes ne sont plus désignées à la main : elles sont
détectées par une RÈGLE, appliquée automatiquement à toute la période.

Une observation ORIGINALE est déclarée aberrante si, à la fois :
    1. elle s'écarte de plus de config.SEUIL_ANOMALIE_SAUT_3H (15 °C) de la
       valeur de la même station 3 h avant (uniquement le passé) ;
    2. elle s'écarte de la valeur prédite AU MÊME INSTANT par ses stations
       voisines de plus que le plus grand écart jamais observé sur la période
       d'apprentissage (seuil appris automatiquement, environ 14 °C).

Les corrélations, les voisins et les régressions sont appris sur la période
d'apprentissage uniquement (avant la fin de 2022) : la règle n'a jamais vu
2023 ni le test 2024-2025.

Les observations détectées sont :
    1. conservées dans un journal ;
    2. remplacées temporairement par NaN ;
    3. réimputées à partir des stations voisines au même instant ;
    4. sauvegardées dans une NOUVELLE matrice finale.

Aucun fichier précédent n'est écrasé.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from src import config, protocole


# =============================================================================
# CONFIGURATION
# =============================================================================


DOSSIER_METEO = config.DOSSIER_METEO_TRAITE

FICHIER_ENTREE = (
    DOSSIER_METEO
    / "temperatures_synop_completes.csv"
)

# Matrice avant toute imputation : sert à savoir quelles valeurs sont des
# observations originales (seules elles peuvent être déclarées aberrantes).
FICHIER_ORIGINAL = (
    DOSSIER_METEO
    / "temperatures_synop_originales.csv"
)

FICHIER_SORTIE = (
    DOSSIER_METEO
    / "temperatures_synop_finales.csv"
)

FICHIER_JOURNAL = (
    DOSSIER_METEO
    / "journal_correction_anomalies.csv"
)


# Nombre maximal de voisins utilisé par la méthode adaptative
N_VOISINS = 3

# Nombre minimal d'observations pour ajuster une régression
MIN_OBSERVATIONS = 100


# =============================================================================
# REGLE DE DETECTION
# =============================================================================

SEUIL_SAUT_3H = config.SEUIL_ANOMALIE_SAUT_3H


# =============================================================================
# OUTILS D'AFFICHAGE
# =============================================================================

def titre(texte):
    print("\n" + "=" * 90)
    print(texte)
    print("=" * 90)


# =============================================================================
# LECTURE DE LA MATRICE
# =============================================================================

def lire_matrice(chemin=None):
    """
    Lit une matrice de températures (par défaut : la matrice complète issue
    de l'imputation temporelle).
    """

    chemin = FICHIER_ENTREE if chemin is None else chemin

    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {chemin}"
        )

    df = pd.read_csv(
        chemin,
        index_col=0,
        parse_dates=True,
    )

    # Les codes WMO doivent rester des chaînes de caractères.
    df.columns = [
        str(col).zfill(5)
        for col in df.columns
    ]

    df = df.sort_index()

    return df


# =============================================================================
# DETECTION DES ANOMALIES
# =============================================================================

def ajuster_modeles_apprentissage(df_original):
    """Apprend, pour chaque station, ses voisins et ses régressions.

    Uniquement sur la période d'apprentissage et sur les observations
    originales. Renvoie {station: (voisins, sous-modèles)}.
    """

    apprentissage = protocole.periode_apprentissage(df_original)
    correlations = calculer_correlations(apprentissage)

    return {
        station: construire_sous_modeles(apprentissage, correlations, station)
        for station in df_original.columns
    }


def residus_spatiaux(df, modeles_par_station):
    """Écart entre chaque valeur et la prédiction de ses voisins au même instant.

    La prédiction utilise le modèle aux 3 voisins (les voisins sont toujours
    disponibles dans la matrice complète). NaN si ce modèle n'existe pas.
    """

    residus = {}

    for station, (voisins, modeles) in modeles_par_station.items():

        cle = tuple(voisins)

        if cle not in modeles:
            residus[station] = pd.Series(np.nan, index=df.index)
            continue

        X = df[voisins].to_numpy(dtype=float)
        complet = ~np.isnan(X).any(axis=1)
        prediction = np.full(len(df), np.nan)
        prediction[complet] = modeles[cle]["modele"].predict(X[complet])
        residus[station] = df[station] - prediction

    return pd.DataFrame(residus, index=df.index)[df.columns]


def seuil_spatial_appris(residus, df_original):
    """Plus grand écart aux voisins observé sur la période d'apprentissage.

    Une observation plus incohérente avec ses voisines que tout ce qui a été
    vu pendant l'apprentissage est suspecte.
    """

    observes = residus.where(df_original.notna())
    return float(protocole.periode_apprentissage(observes).abs().max().max())


def detecter_anomalies(df_complet, df_original, residus, seuil_spatial,
                       seuil_saut=SEUIL_SAUT_3H):
    """Applique la règle à toute la période. Renvoie une ligne par anomalie.

    Seules les observations originales peuvent être déclarées aberrantes.
    Le saut compare chaque valeur à celle de la même station 3 h avant
    (le passé seulement).
    """

    saut = (df_complet - df_complet.shift(1)).abs()

    suspect = (
        df_original.notna()
        & (saut > seuil_saut)
        & (residus.abs() > seuil_spatial)
    )

    lignes = []

    for timestamp, station in suspect.stack().loc[lambda x: x].index:
        lignes.append(
            {
                "timestamp": timestamp,
                "station": station,
                "valeur_originale": float(df_original.loc[timestamp, station]),
                "saut_3h": float(saut.loc[timestamp, station]),
                "ecart_voisins": float(residus.loc[timestamp, station]),
                "raison": (
                    f"saut de {saut.loc[timestamp, station]:.1f} °C en 3 h "
                    f"(> {seuil_saut:.0f}) et écart de "
                    f"{residus.loc[timestamp, station]:.1f} °C aux voisines "
                    f"(> {seuil_spatial:.1f}, maximum de l'apprentissage)"
                ),
            }
        )

    return pd.DataFrame(
        lignes,
        columns=["timestamp", "station", "valeur_originale", "saut_3h",
                 "ecart_voisins", "raison"],
    )


# =============================================================================
# CALCUL DES CORRELATIONS
# =============================================================================

def calculer_correlations(df):
    """
    Calcule la matrice de corrélation.

    Les anomalies doivent déjà avoir été remplacées par NaN
    avant cet appel afin qu'elles ne participent pas au calcul.
    """

    return df.corr(
        method="pearson",
        min_periods=100,
    )


def meilleurs_voisins(
    correlations,
    station,
    n=3,
):
    """
    Retourne les n stations les plus corrélées
    avec la station cible.
    """

    correlations_station = (
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

    return list(
        correlations_station
        .head(n)
        .index
    )


# =============================================================================
# AJUSTEMENT DES SOUS-MODELES
# =============================================================================

def ajuster_modele(
    df,
    station,
    voisins,
):
    """
    Ajuste une régression linéaire multiple :

        station cible
            ~
        températures des voisins

    Seules les lignes complètes pour la cible et
    les voisins sélectionnés sont utilisées.
    """

    colonnes = [
        station,
        *voisins,
    ]

    apprentissage = (
        df[colonnes]
        .dropna()
    )

    if (
        len(apprentissage)
        < MIN_OBSERVATIONS
    ):
        return None

    X = apprentissage[
        voisins
    ].to_numpy()

    y = apprentissage[
        station
    ].to_numpy()

    modele = LinearRegression()

    modele.fit(
        X,
        y,
    )

    return {
        "modele": modele,
        "voisins": voisins,
        "n_apprentissage": len(
            apprentissage
        ),
    }


def construire_sous_modeles(
    df,
    correlations,
    station,
):
    """
    Construit tous les sous-modèles possibles pour une station.

    Avec 3 voisins A, B, C :

        modèle ABC
        modèle AB
        modèle AC
        modèle BC
        modèle A
        modèle B
        modèle C

    Cela reprend le principe de la méthode adaptative utilisée
    lors du benchmark.
    """

    from itertools import combinations

    voisins = meilleurs_voisins(
        correlations,
        station,
        n=N_VOISINS,
    )

    modeles = {}

    # On commence par les modèles utilisant le plus
    # grand nombre de voisins.
    for taille in range(
        len(voisins),
        0,
        -1,
    ):

        for combinaison in combinations(
            voisins,
            taille,
        ):

            combinaison = list(
                combinaison
            )

            resultat = ajuster_modele(
                df,
                station,
                combinaison,
            )

            if resultat is not None:

                cle = tuple(
                    combinaison
                )

                modeles[cle] = resultat

    return voisins, modeles


# =============================================================================
# PREDICTION ADAPTATIVE
# =============================================================================

def predire_adaptatif(
    df,
    timestamp,
    station,
    voisins,
    modeles,
):
    """
    Prédit une température avec le meilleur sous-modèle disponible.

    Priorité :
        3 voisins
        puis 2
        puis 1

    Parmi les modèles de même taille, l'ordre respecte
    l'ordre des meilleurs voisins corrélés.
    """

    from itertools import combinations

    for taille in range(
        len(voisins),
        0,
        -1,
    ):

        for combinaison in combinations(
            voisins,
            taille,
        ):

            cle = tuple(
                combinaison
            )

            if cle not in modeles:
                continue

            valeurs = df.loc[
                timestamp,
                list(combinaison),
            ]

            if valeurs.isna().any():
                continue

            X = np.array(
                valeurs,
                dtype=float,
            ).reshape(
                1,
                -1,
            )

            modele = modeles[
                cle
            ]["modele"]

            prediction = float(
                modele.predict(X)[0]
            )

            return {
                "prediction": prediction,
                "voisins_utilises": list(
                    combinaison
                ),
                "nombre_voisins": taille,
                "n_apprentissage": modeles[
                    cle
                ]["n_apprentissage"],
            }

    return {
        "prediction": np.nan,
        "voisins_utilises": [],
        "nombre_voisins": 0,
        "n_apprentissage": 0,
    }


# =============================================================================
# CORRECTION
# =============================================================================

def corriger_anomalies(df, anomalies, modeles_par_station, noms=None):
    """
    Remplace chaque anomalie détectée par la prédiction de ses voisines au même
    instant (modèles appris sur la période d'apprentissage).
    """

    titre(
        "REIMPUTATION DES ANOMALIES"
    )

    noms = noms or {}
    df_corrige = df.copy()

    # Les anomalies sont retirées AVANT toute prédiction : une anomalie ne peut
    # pas servir à en corriger une autre.
    for ligne in anomalies.itertuples(index=False):
        df_corrige.loc[ligne.timestamp, ligne.station] = np.nan

    journal = []

    for ligne in anomalies.itertuples(index=False):

        voisins, modeles = modeles_par_station[ligne.station]

        resultat = predire_adaptatif(
            df_corrige,
            ligne.timestamp,
            ligne.station,
            voisins,
            modeles,
        )

        prediction = resultat["prediction"]
        statut = "non_corrigee" if pd.isna(prediction) else "corrigee"

        if statut == "corrigee":
            df_corrige.loc[ligne.timestamp, ligne.station] = prediction

        print(
            f"{ligne.timestamp} | {ligne.station} "
            f"{noms.get(ligne.station, '')} | "
            f"{ligne.valeur_originale:.1f} °C -> {prediction:.1f} °C"
        )

        journal.append(
            {
                "timestamp": ligne.timestamp,
                "station": ligne.station,
                "nom_station": noms.get(ligne.station, ""),
                "valeur_originale": ligne.valeur_originale,
                "valeur_corrigee": prediction,
                "voisins_utilises": ",".join(resultat["voisins_utilises"]),
                "nombre_voisins": resultat["nombre_voisins"],
                "observations_apprentissage": resultat["n_apprentissage"],
                "methode": "regression_spatiale_adaptative",
                "raison": ligne.raison,
                "statut": statut,
            }
        )

    journal = pd.DataFrame(
        journal,
        columns=["timestamp", "station", "nom_station", "valeur_originale",
                 "valeur_corrigee", "voisins_utilises", "nombre_voisins",
                 "observations_apprentissage", "methode", "raison", "statut"],
    )

    return df_corrige, journal


# =============================================================================
# CONTROLES FINAUX
# =============================================================================

def controles_finaux(
    df_original,
    df_corrige,
    journal,
):
    """
    Vérifie qu'aucune autre observation n'a été modifiée.
    """

    titre(
        "CONTROLES DE COHERENCE"
    )

    if (
        df_original.shape
        != df_corrige.shape
    ):
        raise AssertionError(
            "Les dimensions ont changé."
        )

    print(
        "Dimensions :",
        df_corrige.shape,
    )

    print(
        "Nombre de NaN :",
        int(
            df_corrige
            .isna()
            .sum()
            .sum()
        ),
    )

    # -------------------------------------------------------------------------
    # Contrôle : seules les anomalies déclarées
    # peuvent avoir changé.
    # -------------------------------------------------------------------------

    masque_autorise = pd.DataFrame(
        False,
        index=df_original.index,
        columns=df_original.columns,
    )

    for ligne in journal.itertuples(index=False):

        masque_autorise.loc[
            ligne.timestamp,
            ligne.station
        ] = True

    difference = (
        ~np.isclose(
            df_original.to_numpy(
                dtype=float
            ),
            df_corrige.to_numpy(
                dtype=float
            ),
            equal_nan=True,
        )
    )

    masque_autorise_array = (
        masque_autorise.to_numpy()
    )

    modifications_non_autorisees = (
        difference
        & ~masque_autorise_array
    )

    nombre_non_autorise = int(
        modifications_non_autorisees.sum()
    )

    nombre_modifications = int(
        difference.sum()
    )

    print(
        "Nombre total de valeurs modifiées :",
        nombre_modifications,
    )

    print(
        "Modifications non autorisées :",
        nombre_non_autorise,
    )

    if nombre_non_autorise != 0:
        raise AssertionError(
            "Des valeurs autres que les anomalies "
            "confirmées ont été modifiées."
        )

    # Toutes les anomalies doivent avoir été corrigées.
    non_corrigees = (
        journal[
            "statut"
        ]
        != "corrigee"
    ).sum()

    print(
        "Anomalies corrigées :",
        int(
            (
                journal["statut"]
                == "corrigee"
            ).sum()
        ),
        "/",
        len(journal),
    )

    if non_corrigees > 0:
        raise AssertionError(
            f"{non_corrigees} anomalie(s) "
            "n'ont pas pu être corrigée(s)."
        )

    print(
        "\nContrôles : OK"
    )


# =============================================================================
# SAUVEGARDE
# =============================================================================

def sauvegarder(
    df_corrige,
    journal,
):
    """
    Sauvegarde la nouvelle matrice finale et le journal.
    """

    titre(
        "SAUVEGARDE"
    )

    DOSSIER_METEO.mkdir(
        parents=True,
        exist_ok=True,
    )

    df_corrige.to_csv(
        FICHIER_SORTIE,
        index=True,
        index_label="timestamp",
    )

    journal.to_csv(
        FICHIER_JOURNAL,
        index=False,
    )

    print(
        "Matrice finale :"
    )

    print(
        FICHIER_SORTIE
    )

    print(
        "\nJournal des corrections :"
    )

    print(
        FICHIER_JOURNAL
    )


# =============================================================================
# MAIN
# =============================================================================

def main():

    titre(
        "CORRECTION CONTROLEE DES ANOMALIES SYNOP"
    )

    print(
        "\nLecture de la matrice complète..."
    )

    df_original = lire_matrice()

    print(
        "Dimensions :",
        df_original.shape,
    )

    print(
        "Première date :",
        df_original.index.min(),
    )

    print(
        "Dernière date :",
        df_original.index.max(),
    )

    print(
        "Valeurs manquantes :",
        int(
            df_original
            .isna()
            .sum()
            .sum()
        ),
    )

    # -------------------------------------------------------------------------
    # Modèles des voisins : appris sur la période d'apprentissage
    # -------------------------------------------------------------------------

    observations = lire_matrice(FICHIER_ORIGINAL)

    titre(
        "APPRENTISSAGE DES VOISINS (PERIODE D'APPRENTISSAGE)"
    )

    modeles_par_station = ajuster_modeles_apprentissage(observations)

    # -------------------------------------------------------------------------
    # Détection par la règle
    # -------------------------------------------------------------------------

    residus = residus_spatiaux(df_original, modeles_par_station)
    seuil_spatial = seuil_spatial_appris(residus, observations)

    titre(
        "DETECTION DES ANOMALIES"
    )

    print(
        f"Règle : saut > {SEUIL_SAUT_3H:.0f} °C en 3 h ET écart aux voisines "
        f"> {seuil_spatial:.2f} °C (maximum observé sur l'apprentissage)"
    )

    anomalies = detecter_anomalies(
        df_original,
        observations,
        residus,
        seuil_spatial,
    )

    print(
        "Anomalies détectées :",
        len(anomalies),
    )

    print(
        anomalies.to_string(index=False)
    )

    # -------------------------------------------------------------------------
    # Correction
    # -------------------------------------------------------------------------

    from src.meteo import lire_liste_stations_officielles

    noms = dict(
        zip(
            lire_liste_stations_officielles()["ID"].astype(str).str.zfill(5),
            lire_liste_stations_officielles()["Nom"],
        )
    )

    df_corrige, journal = (
        corriger_anomalies(
            df_original,
            anomalies,
            modeles_par_station,
            noms,
        )
    )

    # -------------------------------------------------------------------------
    # Contrôles
    # -------------------------------------------------------------------------

    controles_finaux(
        df_original,
        df_corrige,
        journal,
    )

    # -------------------------------------------------------------------------
    # Résumé
    # -------------------------------------------------------------------------

    titre(
        "BILAN DES CORRECTIONS"
    )

    colonnes_affichage = [
        "timestamp",
        "station",
        "nom_station",
        "valeur_originale",
        "valeur_corrigee",
        "voisins_utilises",
        "nombre_voisins",
        "statut",
    ]

    print(
        journal[
            colonnes_affichage
        ].to_string(
            index=False
        )
    )

    # -------------------------------------------------------------------------
    # Sauvegarde
    # -------------------------------------------------------------------------

    sauvegarder(
        df_corrige,
        journal,
    )

    titre(
        "CORRECTION TERMINEE"
    )

    print(
        "Le fichier temperatures_synop_completes.csv "
        "n'a pas été modifié."
    )

    print(
        "La matrice corrigée est enregistrée dans "
        "temperatures_synop_finales.csv."
    )

    print(
        "\nIMPORTANT : seules les observations détectées par la règle "
        "ont été corrigées."
    )


if __name__ == "__main__":
    main()