"""
Correction contrôlée des anomalies météorologiques SYNOP.

Ce script intervient APRES :
    1. l'imputation spatiale ;
    2. l'imputation temporelle ;
    3. le diagnostic des anomalies.

Principe
--------
Deux observations originales ont été identifiées comme fortement incohérentes
à la fois temporellement et spatialement :

    - MARIGNANE (07650)
      2023-08-09 09:00 UTC
      valeur originale : 0.0 °C

    - ST GIRONS (07627)
      2025-09-23 15:00 UTC
      valeur originale : -11.3 °C

Ces observations sont :
    1. conservées dans un journal ;
    2. remplacées temporairement par NaN ;
    3. réimputées à partir de stations voisines fortement corrélées ;
    4. sauvegardées dans une NOUVELLE matrice finale.

Aucun fichier précédent n'est écrasé.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


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
    / "temperatures_synop_completes.csv"
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
# ANOMALIES CONFIRMEES
# =============================================================================

ANOMALIES = [
    {
        "station": "07650",
        "timestamp": "2023-08-09 09:00:00+00:00",
        "valeur_attendue": 0.0,
        "nom_station": "MARIGNANE",
        "raison": (
            "Incoherence spatio-temporelle forte : valeur de 0.0 °C "
            "alors que les stations voisines présentent environ 23 à 30 °C."
        ),
    },
    {
        "station": "07627",
        "timestamp": "2025-09-23 15:00:00+00:00",
        "valeur_attendue": -11.3,
        "nom_station": "ST GIRONS",
        "raison": (
            "Incoherence spatio-temporelle forte : valeur de -11.3 °C "
            "alors que les stations voisines présentent environ 9 à 16 °C."
        ),
    },
]


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

def lire_matrice():
    """
    Lit la matrice complète issue de l'imputation temporelle.
    """

    if not FICHIER_ENTREE.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {FICHIER_ENTREE}"
        )

    df = pd.read_csv(
        FICHIER_ENTREE,
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
# CONTROLE DES ANOMALIES
# =============================================================================

def verifier_anomalies(df):
    """
    Vérifie que les observations à corriger existent réellement
    et correspondent aux valeurs diagnostiquées.
    """

    titre("CONTROLE DES ANOMALIES A CORRIGER")

    controles = []

    for anomalie in ANOMALIES:

        station = anomalie["station"]

        timestamp = pd.Timestamp(
            anomalie["timestamp"]
        )

        valeur_attendue = anomalie[
            "valeur_attendue"
        ]

        if station not in df.columns:
            raise ValueError(
                f"Station absente : {station}"
            )

        if timestamp not in df.index:
            raise ValueError(
                f"Timestamp absent : {timestamp}"
            )

        valeur = df.loc[
            timestamp,
            station
        ]

        difference = abs(
            float(valeur)
            - float(valeur_attendue)
        )

        conforme = difference < 1e-6

        controles.append(
            {
                "station": station,
                "nom_station": anomalie[
                    "nom_station"
                ],
                "timestamp": timestamp,
                "valeur_trouvee": valeur,
                "valeur_attendue": valeur_attendue,
                "controle_ok": conforme,
            }
        )

        print(
            f"\n{station} - "
            f"{anomalie['nom_station']}"
        )

        print(
            f"Timestamp : {timestamp}"
        )

        print(
            f"Valeur trouvée : "
            f"{valeur:.3f} °C"
        )

        print(
            f"Valeur attendue : "
            f"{valeur_attendue:.3f} °C"
        )

        print(
            "Contrôle : "
            + ("OK" if conforme else "ECHEC")
        )

        if not conforme:
            raise ValueError(
                "La valeur présente dans le fichier "
                "ne correspond pas à celle diagnostiquée. "
                "Correction interrompue."
            )

    return pd.DataFrame(controles)


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

def corriger_anomalies(df):
    """
    Corrige uniquement les anomalies explicitement confirmées.
    """

    titre(
        "PREPARATION DE LA CORRECTION"
    )

    df_corrige = df.copy()

    valeurs_originales = {}

    # -------------------------------------------------------------------------
    # 1. Sauvegarde des valeurs originales
    # -------------------------------------------------------------------------

    for anomalie in ANOMALIES:

        station = anomalie[
            "station"
        ]

        timestamp = pd.Timestamp(
            anomalie["timestamp"]
        )

        valeur = df_corrige.loc[
            timestamp,
            station
        ]

        valeurs_originales[
            (timestamp, station)
        ] = float(valeur)

        print(
            f"{timestamp} | "
            f"{station} | "
            f"{valeur:.3f} °C "
            f"-> NaN temporaire"
        )

        # Important :
        # l'anomalie est retirée AVANT le calcul
        # des corrélations et des régressions.
        df_corrige.loc[
            timestamp,
            station
        ] = np.nan

    # -------------------------------------------------------------------------
    # 2. Corrélations recalculées sans les anomalies
    # -------------------------------------------------------------------------

    titre(
        "RECALCUL DES CORRELATIONS SANS LES ANOMALIES"
    )

    correlations = calculer_correlations(
        df_corrige
    )

    print(
        "Dimensions :",
        correlations.shape,
    )

    # -------------------------------------------------------------------------
    # 3. Correction de chaque anomalie
    # -------------------------------------------------------------------------

    titre(
        "REIMPUTATION DES ANOMALIES"
    )

    journal = []

    for anomalie in ANOMALIES:

        station = anomalie[
            "station"
        ]

        nom_station = anomalie[
            "nom_station"
        ]

        timestamp = pd.Timestamp(
            anomalie["timestamp"]
        )

        valeur_originale = (
            valeurs_originales[
                (timestamp, station)
            ]
        )

        voisins, modeles = (
            construire_sous_modeles(
                df_corrige,
                correlations,
                station,
            )
        )

        print(
            f"\n{station} - "
            f"{nom_station}"
        )

        print(
            "Meilleurs voisins : "
            + ", ".join(voisins)
        )

        print(
            "Nombre de sous-modèles : "
            f"{len(modeles)}"
        )

        resultat = predire_adaptatif(
            df_corrige,
            timestamp,
            station,
            voisins,
            modeles,
        )

        prediction = resultat[
            "prediction"
        ]

        if pd.isna(prediction):

            print(
                "ECHEC : aucune prédiction "
                "possible."
            )

            statut = "non_corrigee"

        else:

            df_corrige.loc[
                timestamp,
                station
            ] = prediction

            print(
                f"Valeur originale : "
                f"{valeur_originale:.3f} °C"
            )

            print(
                f"Valeur corrigée : "
                f"{prediction:.3f} °C"
            )

            print(
                "Voisins utilisés : "
                + ", ".join(
                    resultat[
                        "voisins_utilises"
                    ]
                )
            )

            print(
                "Nombre de voisins : "
                f"{resultat['nombre_voisins']}"
            )

            statut = "corrigee"

        journal.append(
            {
                "timestamp": timestamp,
                "station": station,
                "nom_station": nom_station,
                "valeur_originale": (
                    valeur_originale
                ),
                "valeur_corrigee": (
                    prediction
                ),
                "voisins_utilises": ",".join(
                    resultat[
                        "voisins_utilises"
                    ]
                ),
                "nombre_voisins": resultat[
                    "nombre_voisins"
                ],
                "observations_apprentissage": (
                    resultat[
                        "n_apprentissage"
                    ]
                ),
                "methode": (
                    "regression_spatiale_adaptative"
                ),
                "raison": anomalie[
                    "raison"
                ],
                "statut": statut,
            }
        )

    journal = pd.DataFrame(
        journal
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

    for anomalie in ANOMALIES:

        timestamp = pd.Timestamp(
            anomalie["timestamp"]
        )

        station = anomalie[
            "station"
        ]

        masque_autorise.loc[
            timestamp,
            station
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
    # Vérification avant toute modification
    # -------------------------------------------------------------------------

    verifier_anomalies(
        df_original
    )

    # -------------------------------------------------------------------------
    # Correction
    # -------------------------------------------------------------------------

    df_corrige, journal = (
        corriger_anomalies(
            df_original
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
        "\nIMPORTANT : seules les deux anomalies "
        "explicitement validées ont été corrigées."
    )


if __name__ == "__main__":
    main()