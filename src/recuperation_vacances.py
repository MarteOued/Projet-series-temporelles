"""Récupération du calendrier scolaire officiel.

Source :
Ministère de l'Éducation nationale
https://data.education.gouv.fr/

Ce module récupère les données brutes du calendrier scolaire via
l'API officielle et les sauvegarde dans data/raw/.

Aucune transformation métier n'est réalisée ici.
"""

import pandas as pd
import requests

from src.config import DATA_RAW


URL_API = (
    "https://data.education.gouv.fr/api/explore/v2.1/catalog/"
    "datasets/fr-en-calendrier-scolaire/records"
)

FICHIER_SORTIE = DATA_RAW / "calendrier_scolaire.csv"


def recuperer_vacances_scolaires():
    """Récupère le calendrier scolaire depuis l'API officielle.

    Returns
    -------
    pandas.DataFrame
        Données brutes retournées par l'API.
    """

    # Première requête pour connaître le nombre total
    # d'enregistrements disponibles.
    reponse = requests.get(
        URL_API,
        params={"limit": 1},
        timeout=30,
    )

    reponse.raise_for_status()

    contenu = reponse.json()
    total = contenu["total_count"]

    print(f"Nombre d'enregistrements annoncé par l'API : {total}")

    # L'API Explore limite le nombre d'observations par requête.
    # On récupère donc les données par blocs.
    taille_bloc = 100
    observations = []

    for offset in range(0, total, taille_bloc):

        reponse = requests.get(
            URL_API,
            params={
                "limit": taille_bloc,
                "offset": offset,
            },
            timeout=30,
        )

        reponse.raise_for_status()

        bloc = reponse.json()["results"]
        observations.extend(bloc)

        print(
            f"Récupération : "
            f"{len(observations)}/{total} enregistrements"
        )

    # Conversion des observations brutes en DataFrame.
    donnees = pd.DataFrame(observations)

    # Création du dossier raw s'il n'existe pas.
    DATA_RAW.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Sauvegarde sans transformation.
    donnees.to_csv(
        FICHIER_SORTIE,
        index=False,
        encoding="utf-8",
    )

    print()
    print(f"Fichier enregistré : {FICHIER_SORTIE}")
    print(f"Dimensions : {donnees.shape}")

    return donnees


if __name__ == "__main__":
    recuperer_vacances_scolaires()