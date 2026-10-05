"""Gestion des observations météorologiques SYNOP de Météo-France.

Ce module permet :

1. de récupérer les archives annuelles SYNOP ;
2. de lire proprement les fichiers CSV compressés ;
3. d'identifier les stations présentes chaque année sur la période du projet ;
4. d'identifier les stations situées en France métropolitaine ;
5. de construire l'ensemble des stations stables métropolitaines.

Les fichiers bruts sont conservés sans modification dans :

    data/donnees-brutes/meteo/

Période du projet :
    décembre 2015 -> décembre 2025

Important
---------
La sélection des stations est indépendante de la gestion des valeurs
manquantes. Une station est dite "stable" si elle est présente dans
chacune des archives annuelles 2015-2025.

L'appartenance à la France métropolitaine est déterminée à partir des
contours officiels des 13 régions métropolitaines. Une tolérance
géographique de 100 mètres est appliquée après projection en Lambert-93
afin de ne pas exclure artificiellement certaines stations littorales.
"""

import json
from pathlib import Path

import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform

from src.config import DATA_BRUTES, DATA_DEBUT, DATA_FIN


# =============================================================================
# CONFIGURATION
# =============================================================================

DATASET_ID = "686f8595b351c06a3a790867"

URL_DATASET = (
    f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"
)

DOSSIER_METEO_BRUT = DATA_BRUTES / "meteo"

ANNEE_DEBUT = DATA_DEBUT.year
ANNEE_FIN = DATA_FIN.year

FICHIER_STATIONS = (
    DOSSIER_METEO_BRUT / "liste_stations_synop.csv"
)

FICHIER_POSTES_GEOJSON = (
    DOSSIER_METEO_BRUT / "postes_synop.geojson"
)

FICHIER_REGIONS = (
    DOSSIER_METEO_BRUT / "regions_2025.geojson"
)


# Codes INSEE des 13 régions métropolitaines.
CODES_REGIONS_METROPOLE = {
    "11",  # Île-de-France
    "24",  # Centre-Val de Loire
    "27",  # Bourgogne-Franche-Comté
    "28",  # Normandie
    "32",  # Hauts-de-France
    "44",  # Grand Est
    "52",  # Pays de la Loire
    "53",  # Bretagne
    "75",  # Nouvelle-Aquitaine
    "76",  # Occitanie
    "84",  # Auvergne-Rhône-Alpes
    "93",  # Provence-Alpes-Côte d'Azur
    "94",  # Corse
}


# Tolérance utilisée pour les stations situées très près du littoral.
TOLERANCE_LITTORAL_METRES = 100


# Colonnes numériques principales utilisées dans les archives SYNOP.
COLONNES_NUMERIQUES_SYNOP = [
    "lat",
    "lon",
    "t",
]


# =============================================================================
# CATALOGUE DATA.GOUV.FR
# =============================================================================

def recuperer_catalogue():
    """Récupère les métadonnées du jeu Archive Synop OMM."""

    reponse = requests.get(
        URL_DATASET,
        timeout=30,
    )

    reponse.raise_for_status()

    return reponse.json()


def trouver_ressources_synop(catalogue):
    """Trouve les archives SYNOP correspondant à la période du projet.

    Parameters
    ----------
    catalogue : dict
        Métadonnées du jeu de données Data.gouv.fr.

    Returns
    -------
    dict
        Dictionnaire de la forme :

        {
            2015: "https://.../synop_2015.csv.gz",
            ...
            2025: "https://.../synop_2025.csv.gz",
        }
    """

    ressources = {}

    for ressource in catalogue.get("resources", []):

        titre = ressource.get("title", "")
        url = ressource.get("url", "")

        for annee in range(
            ANNEE_DEBUT,
            ANNEE_FIN + 1,
        ):

            if titre == f"synop_{annee}":
                ressources[annee] = url

    return ressources


# =============================================================================
# TELECHARGEMENT
# =============================================================================

def telecharger_fichier(url, destination):
    """Télécharge une ressource si elle n'existe pas déjà."""

    destination = Path(destination)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():

        print(
            f"Déjà présent : {destination.name}"
        )

        return destination

    print(
        f"Téléchargement : {destination.name}"
    )

    with requests.get(
        url,
        stream=True,
        timeout=120,
    ) as reponse:

        reponse.raise_for_status()

        with destination.open("wb") as fichier:

            for bloc in reponse.iter_content(
                chunk_size=1024 * 1024
            ):

                if bloc:
                    fichier.write(bloc)

    return destination


def telecharger_archives_synop():
    """Télécharge toutes les archives SYNOP nécessaires au projet."""

    DOSSIER_METEO_BRUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    catalogue = recuperer_catalogue()

    ressources = trouver_ressources_synop(
        catalogue
    )

    annees_attendues = set(
        range(
            ANNEE_DEBUT,
            ANNEE_FIN + 1,
        )
    )

    annees_trouvees = set(
        ressources
    )

    manquantes = sorted(
        annees_attendues
        - annees_trouvees
    )

    if manquantes:

        raise RuntimeError(
            "Archives SYNOP introuvables pour les années : "
            + ", ".join(
                map(str, manquantes)
            )
        )

    fichiers = []

    for annee in sorted(ressources):

        destination = (
            DOSSIER_METEO_BRUT
            / f"synop_{annee}.csv.gz"
        )

        fichier = telecharger_fichier(
            ressources[annee],
            destination,
        )

        fichiers.append(fichier)

    return fichiers


# =============================================================================
# LECTURE DES ARCHIVES SYNOP
# =============================================================================

def chemin_archive_synop(annee):
    """Retourne le chemin de l'archive SYNOP d'une année."""

    if not (
        ANNEE_DEBUT
        <= annee
        <= ANNEE_FIN
    ):

        raise ValueError(
            f"L'année {annee} est hors de la période "
            f"{ANNEE_DEBUT}-{ANNEE_FIN}."
        )

    return (
        DOSSIER_METEO_BRUT
        / f"synop_{annee}.csv.gz"
    )


def lire_archive_synop(annee):
    """Lit une archive annuelle SYNOP.

    Le séparateur des fichiers SYNOP est le point-virgule.

    Le code OMM est conservé sous forme de texte afin de préserver
    les zéros initiaux.

    ``validity_time`` est converti en datetime UTC et les principales
    variables numériques sont converties explicitement.
    """

    chemin = chemin_archive_synop(
        annee
    )

    if not chemin.exists():

        raise FileNotFoundError(
            f"Archive SYNOP absente : {chemin}"
        )

    donnees = pd.read_csv(
        chemin,
        sep=";",
        compression="gzip",
        dtype={
            "geo_id_wmo": "string",
        },
        low_memory=False,
    )

    if "validity_time" in donnees.columns:

        donnees["validity_time"] = (
            pd.to_datetime(
                donnees["validity_time"],
                utc=True,
                errors="coerce",
            )
        )

    for colonne in COLONNES_NUMERIQUES_SYNOP:

        if colonne in donnees.columns:

            donnees[colonne] = (
                pd.to_numeric(
                    donnees[colonne],
                    errors="coerce",
                )
            )

    return donnees


# =============================================================================
# STATIONS PRESENTES DANS LES ARCHIVES
# =============================================================================

def stations_par_annee():
    """Retourne les stations observées dans chaque archive annuelle.

    Returns
    -------
    pandas.DataFrame
        Une ligne par couple année/station.
    """

    resultats = []

    for annee in range(
        ANNEE_DEBUT,
        ANNEE_FIN + 1,
    ):

        donnees = lire_archive_synop(
            annee
        )

        colonnes = [
            "geo_id_wmo",
            "name",
            "lat",
            "lon",
        ]

        stations = (
            donnees[colonnes]
            .dropna(
                subset=["geo_id_wmo"]
            )
            .drop_duplicates(
                subset=["geo_id_wmo"]
            )
            .copy()
        )

        stations["annee"] = annee

        resultats.append(
            stations
        )

    return pd.concat(
        resultats,
        ignore_index=True,
    )


def stations_stables():
    """Identifie les stations présentes chaque année du projet.

    Une station est considérée comme stable si son code OMM apparaît
    dans chacune des archives annuelles comprises entre ANNEE_DEBUT
    et ANNEE_FIN.

    Aucun critère de taux de valeurs manquantes n'est appliqué ici.

    Returns
    -------
    pandas.DataFrame
        Stations présentes chaque année, avec :

        - geo_id_wmo
        - name
        - latitude
        - longitude
        - nb_annees
    """

    donnees = stations_par_annee()

    nombre_annees_attendu = (
        ANNEE_FIN
        - ANNEE_DEBUT
        + 1
    )

    comptes = (
        donnees
        .groupby(
            "geo_id_wmo",
            as_index=False,
        )
        .agg(
            nb_annees=(
                "annee",
                "nunique",
            ),
            name=(
                "name",
                "first",
            ),
            latitude=(
                "lat",
                "median",
            ),
            longitude=(
                "lon",
                "median",
            ),
        )
    )

    stables = (
        comptes[
            comptes["nb_annees"]
            == nombre_annees_attendu
        ]
        .copy()
        .sort_values(
            "geo_id_wmo"
        )
        .reset_index(drop=True)
    )

    return stables


# =============================================================================
# LISTE OFFICIELLE DES STATIONS
# =============================================================================

def lire_liste_stations_officielles():
    """Lit la liste officielle des stations SYNOP utilisée dans le projet."""

    if not FICHIER_STATIONS.exists():

        raise FileNotFoundError(
            "Liste officielle des stations SYNOP absente : "
            f"{FICHIER_STATIONS}"
        )

    stations = pd.read_csv(
        FICHIER_STATIONS,
        sep=";",
        dtype={
            "ID": "string",
        },
    )

    colonnes_attendues = {
        "ID",
        "Nom",
        "Latitude",
        "Longitude",
    }

    manquantes = (
        colonnes_attendues
        - set(stations.columns)
    )

    if manquantes:

        raise ValueError(
            "Colonnes absentes de la liste des stations : "
            + ", ".join(
                sorted(manquantes)
            )
        )

    stations["Latitude"] = pd.to_numeric(
        stations["Latitude"],
        errors="coerce",
    )

    stations["Longitude"] = pd.to_numeric(
        stations["Longitude"],
        errors="coerce",
    )

    return stations


# =============================================================================
# REGIONS METROPOLITAINES
# =============================================================================

def lire_regions_metropolitaines():
    """Lit les contours des 13 régions métropolitaines.

    Returns
    -------
    list of dict
        Chaque élément contient :

        - code_region
        - region
        - geometry

    La géométrie retournée est initialement en WGS84 (EPSG:4326).
    """

    if not FICHIER_REGIONS.exists():

        raise FileNotFoundError(
            "Fichier des régions absent : "
            f"{FICHIER_REGIONS}"
        )

    with FICHIER_REGIONS.open(
        encoding="utf-8"
    ) as fichier:

        geojson = json.load(
            fichier
        )

    regions = []

    for feature in geojson["features"]:

        proprietes = feature[
            "properties"
        ]

        code = str(
            proprietes["code"]
        )

        if (
            code
            not in CODES_REGIONS_METROPOLE
        ):
            continue

        regions.append(
            {
                "code_region": code,
                "region": proprietes["nom"],
                "geometry": shape(
                    feature["geometry"]
                ),
            }
        )

    return regions


def regions_metropolitaines_projetees(
    tolerance_metres=TOLERANCE_LITTORAL_METRES,
):
    """Projette les régions en Lambert-93 et applique une tolérance.

    La projection EPSG:2154 permet d'exprimer la tolérance en mètres.

    La tolérance de 100 mètres évite qu'une station littorale soit
    artificiellement considérée hors métropole à cause des différences
    de précision entre les coordonnées de la station et le contour
    géographique.
    """

    if tolerance_metres < 0:

        raise ValueError(
            "La tolérance géographique doit être positive ou nulle."
        )

    regions = (
        lire_regions_metropolitaines()
    )

    vers_lambert93 = (
        Transformer.from_crs(
            "EPSG:4326",
            "EPSG:2154",
            always_xy=True,
        ).transform
    )

    resultat = []

    for region in regions:

        geometrie = transform(
            vers_lambert93,
            region["geometry"],
        )

        if tolerance_metres > 0:

            geometrie = (
                geometrie.buffer(
                    tolerance_metres
                )
            )

        resultat.append(
            {
                "code_region": (
                    region["code_region"]
                ),
                "region": (
                    region["region"]
                ),
                "geometry": geometrie,
            }
        )

    return resultat


# =============================================================================
# CLASSEMENT GEOGRAPHIQUE DES STATIONS
# =============================================================================

def classer_stations_par_region(
    tolerance_metres=TOLERANCE_LITTORAL_METRES,
):
    """Associe chaque station officielle à une région métropolitaine.

    Les stations ne correspondant à aucune des 13 régions métropolitaines
    conservent une région manquante.

    Returns
    -------
    pandas.DataFrame
        Colonnes principales :

        - geo_id_wmo
        - name
        - latitude
        - longitude
        - code_region
        - region
    """

    stations = (
        lire_liste_stations_officielles()
    )

    regions = (
        regions_metropolitaines_projetees(
            tolerance_metres=tolerance_metres
        )
    )

    vers_lambert93 = (
        Transformer.from_crs(
            "EPSG:4326",
            "EPSG:2154",
            always_xy=True,
        ).transform
    )

    resultats = []

    for _, station in stations.iterrows():

        latitude = station["Latitude"]
        longitude = station["Longitude"]

        code_region = None
        nom_region = None

        if (
            pd.notna(latitude)
            and pd.notna(longitude)
        ):

            point = Point(
                float(longitude),
                float(latitude),
            )

            point_projete = transform(
                vers_lambert93,
                point,
            )

            for region in regions:

                if region["geometry"].covers(
                    point_projete
                ):

                    code_region = (
                        region["code_region"]
                    )

                    nom_region = (
                        region["region"]
                    )

                    break

        resultats.append(
            {
                "geo_id_wmo": (
                    station["ID"]
                ),
                "name": (
                    station["Nom"]
                ),
                "latitude": latitude,
                "longitude": longitude,
                "code_region": code_region,
                "region": nom_region,
            }
        )

    return pd.DataFrame(
        resultats
    )


def stations_metropolitaines(
    tolerance_metres=TOLERANCE_LITTORAL_METRES,
):
    """Retourne les stations officielles situées en métropole."""

    classement = (
        classer_stations_par_region(
            tolerance_metres=tolerance_metres
        )
    )

    metro = (
        classement[
            classement["code_region"]
            .notna()
        ]
        .copy()
        .sort_values(
            ["region", "geo_id_wmo"]
        )
        .reset_index(drop=True)
    )

    return metro


# =============================================================================
# STATIONS STABLES METROPOLITAINES
# =============================================================================

def stations_stables_metropolitaines(
    tolerance_metres=TOLERANCE_LITTORAL_METRES,
):
    """Retourne les stations à la fois stables et métropolitaines.

    La sélection repose sur deux critères indépendants :

    1. présence de la station dans chacune des archives annuelles ;
    2. appartenance géographique à l'une des 13 régions métropolitaines.

    Aucun seuil sur le taux de données manquantes n'est appliqué ici.

    Returns
    -------
    pandas.DataFrame
        Une ligne par station retenue.
    """

    stables = stations_stables()

    metro = stations_metropolitaines(
        tolerance_metres=tolerance_metres
    )

    # On conserve le nom et les coordonnées provenant des archives
    # historiques, puis on ajoute uniquement l'information régionale.
    informations_geographiques = (
        metro[
            [
                "geo_id_wmo",
                "code_region",
                "region",
            ]
        ]
        .copy()
    )

    finales = stables.merge(
        informations_geographiques,
        on="geo_id_wmo",
        how="inner",
        validate="one_to_one",
    )

    finales = (
        finales
        .sort_values(
            ["region", "geo_id_wmo"]
        )
        .reset_index(drop=True)
    )

    return finales


# =============================================================================
# RESUME
# =============================================================================

def resume_selection_stations():
    """Affiche un résumé de la sélection des stations météo."""

    officielles = (
        lire_liste_stations_officielles()
    )

    stables = (
        stations_stables()
    )

    metro = (
        stations_metropolitaines()
    )

    finales = (
        stations_stables_metropolitaines()
    )

    print("=" * 72)
    print("SELECTION DES STATIONS SYNOP")
    print("=" * 72)

    print(
        f"Stations officielles             : {len(officielles)}"
    )

    print(
        f"Stations stables 2015-2025       : {len(stables)}"
    )

    print(
        f"Stations métropolitaines         : {len(metro)}"
    )

    print(
        f"Stations stables métropolitaines : {len(finales)}"
    )

    print()

    print("COUVERTURE REGIONALE")
    print("-" * 72)

    print(
        finales["region"]
        .value_counts()
        .sort_index()
    )

    return finales


# =============================================================================
# EXECUTION
# =============================================================================

def main():
    """Télécharge les archives SYNOP nécessaires au projet."""

    fichiers = (
        telecharger_archives_synop()
    )

    print()

    print(
        f"{len(fichiers)} archives SYNOP disponibles."
    )

    print(
        f"Période : {ANNEE_DEBUT} -> {ANNEE_FIN}"
    )


if __name__ == "__main__":
    main()