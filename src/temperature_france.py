"""Températures France CANDIDATES, sur une grille horaire (aucun choix n'est fait ici).

Le choix de la représentation se fera sur la validation 2023 uniquement (décision 8),
en comparant le modèle avec température (M2) pour chacune des trois candidates :

- temp_8_villes    : moyenne des 8 grandes villes du choix de départ (config.STATIONS_8_VILLES) ;
- temp_38_simple   : moyenne simple des stations continentales (les 40 stations stables
                     moins la Corse : la consommation RTE ne couvre pas la Corse) ;
- temp_38_ponderee : moyenne des stations de chaque région, puis moyenne des régions
                     pondérée par leur part de la consommation RTE. Les poids sont calculés
                     sur la période d'apprentissage (2016-2022) uniquement.

Deux versions de chaque température :

- version OPÉRATIONNELLE (colonnes sans suffixe) : chaque heure reçoit la DERNIÈRE observation
  disponible (report vers l'avant), jamais d'interpolation. Interpoler entre deux observations
  SYNOP utiliserait l'observation suivante, encore inconnue au moment de la prévision.
- version MÉTÉO PARFAITE (suffixe `_meteo_parfaite`) : interpolation linéaire entre les
  observations. Réservée au scénario « météo parfaite » (borne de performance), jamais
  présentée comme déployable.

Attention pour la suite (construction des variables à 14 h) : la valeur opérationnelle à
l'heure h est la dernière observation de validité <= h. Pour une prévision faite à 14 h le
jour J, il faut lire la valeur à l'instant `protocole.limite_meteo_connue(J)` (13 h, heure de
Paris), ce qui donne la dernière observation autorisée par le protocole (12 h UTC l'hiver,
9 h UTC l'été).

Lancer depuis la racine du projet : python -m src.temperature_france
"""
import pandas as pd
import requests

from src import config, meteo

FICHIER_TEMPERATURES_STATIONS = config.DOSSIER_METEO_TRAITE / "temperatures_synop_finales.csv"
FICHIER_CONSO_REGIONALE = config.DATA_BRUTES / "rte" / "conso_regionale_apprentissage.csv"
DOSSIER_SORTIE = config.DATA_PREPAREES / "meteo"
FICHIER_SORTIE = DOSSIER_SORTIE / "temperatures_france_candidates_horaire_utc.csv"
FICHIER_POIDS = DOSSIER_SORTIE / "poids_regionaux_apprentissage.csv"

URL_CONSO_REGIONALE = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "eco2mix-regional-cons-def/records"
)


# --- Entrées -------------------------------------------------------------------
def lire_temperatures_stations(chemin=FICHIER_TEMPERATURES_STATIONS):
    """Matrice finale des stations (toutes les 3 h, UTC) issue du pipeline météo."""
    df = pd.read_csv(chemin, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df.columns = [str(c).zfill(5) for c in df.columns]
    return df.sort_index()


def regions_des_stations(codes):
    """Code INSEE de la région de chaque station (d'après les contours officiels)."""
    classement = meteo.classer_stations_par_region()
    classement["geo_id_wmo"] = classement["geo_id_wmo"].astype(str).str.zfill(5)
    regions = classement.set_index("geo_id_wmo")["code_region"]
    return regions.reindex(codes)


def telecharger_conso_regionale():
    """Consommation totale de chaque région sur la période d'apprentissage (RTE).

    Bornes en heure de Paris : du premier jour de l'apprentissage au dernier
    (config.DECOUPAGE). 2023 et le test 2024-2025 ne sont pas utilisés.
    """
    if FICHIER_CONSO_REGIONALE.exists():
        return pd.read_csv(FICHIER_CONSO_REGIONALE, dtype={"code_insee_region": str})

    debut, fin = config.DECOUPAGE["apprentissage"]
    # Bornes en heure de Paris, converties en instants précis (le champ "date"
    # de ce jeu est du texte, que l'API ne sait pas comparer).
    debut_iso = pd.Timestamp(debut, tz=config.FUSEAU).isoformat()
    fin_iso = (pd.Timestamp(fin, tz=config.FUSEAU) + pd.Timedelta(days=1)).isoformat()
    reponse = requests.get(URL_CONSO_REGIONALE, params={
        "select": "code_insee_region, libelle_region, sum(consommation) as consommation_totale",
        "where": f"date_heure >= date'{debut_iso}' and date_heure < date'{fin_iso}'",
        "group_by": "code_insee_region, libelle_region",
        "limit": 50,
    }, timeout=300)
    reponse.raise_for_status()
    conso = pd.DataFrame(reponse.json()["results"])
    conso["code_insee_region"] = conso["code_insee_region"].astype(str)

    FICHIER_CONSO_REGIONALE.parent.mkdir(parents=True, exist_ok=True)
    conso.to_csv(FICHIER_CONSO_REGIONALE, index=False)
    return conso


def poids_regionaux(conso_regionale):
    """Part de chaque région dans la consommation (somme = 1), indexée par code INSEE."""
    conso = conso_regionale.set_index("code_insee_region")["consommation_totale"].astype(float)
    return conso / conso.sum()


# --- Les trois candidates (grille SYNOP de 3 h) --------------------------------
def stations_continentales(regions):
    """Stations hors des régions exclues (la Corse)."""
    return [code for code, region in regions.items()
            if pd.notna(region) and region not in config.REGIONS_EXCLUES_TEMPERATURE_FRANCE]


def temperature_8_villes(temperatures):
    return temperatures[list(config.STATIONS_8_VILLES.values())].mean(axis=1)


def temperature_38_simple(temperatures, regions):
    return temperatures[stations_continentales(regions)].mean(axis=1)


def temperature_38_ponderee(temperatures, regions, poids):
    """Moyenne des stations de chaque région, puis moyenne pondérée des régions."""
    continentales = stations_continentales(regions)
    par_region = temperatures[continentales].T.groupby(regions[continentales]).mean().T
    regions_sans_station = set(poids.index) - set(par_region.columns)
    if regions_sans_station:
        raise ValueError(f"Régions sans station : {sorted(regions_sans_station)}")
    poids = poids.reindex(par_region.columns)
    return par_region.mul(poids, axis=1).sum(axis=1) / poids.sum()


def candidates_3h(temperatures, regions, poids):
    """Les trois températures France sur la grille des observations (3 h, UTC)."""
    return pd.DataFrame({
        "temp_8_villes": temperature_8_villes(temperatures),
        "temp_38_simple": temperature_38_simple(temperatures, regions),
        "temp_38_ponderee": temperature_38_ponderee(temperatures, regions, poids),
    })


# --- Passage à la grille horaire -----------------------------------------------
def vers_horaire(candidates, fin=None):
    """Grille horaire UTC : version opérationnelle (report) et version météo parfaite.

    Opérationnelle : chaque heure prend la dernière observation dont l'heure de
    validité est <= cette heure (aucune observation future).
    Météo parfaite : interpolation linéaire entre observations (scénario plafond).
    """
    fin = candidates.index.max() if fin is None else fin
    grille = pd.date_range(candidates.index.min(), fin, freq="1h", name="date_heure_utc")
    operationnelle = candidates.reindex(grille).ffill()
    parfaite = (
        candidates.reindex(grille.union(candidates.index))
        .interpolate(method="time", limit_area="inside")
        .reindex(grille)
        .add_suffix("_meteo_parfaite")
    )
    return pd.concat([operationnelle, parfaite], axis=1)


def preparer():
    """Construit et sauvegarde les trois candidates sur la grille horaire."""
    temperatures = lire_temperatures_stations()
    regions = regions_des_stations(temperatures.columns)
    if regions.isna().any():
        raise ValueError(f"Stations sans région : {list(regions[regions.isna()].index)}")

    poids = poids_regionaux(telecharger_conso_regionale())
    candidates = candidates_3h(temperatures, regions, poids)

    # Dernière heure : 23 h UTC le dernier jour (couvre la fin de la période en heure de Paris)
    fin = candidates.index.max().normalize() + pd.Timedelta(hours=23)
    horaire = vers_horaire(candidates, fin)

    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    horaire.to_csv(FICHIER_SORTIE)
    poids.rename("part_conso_apprentissage").rename_axis("code_insee_region").to_csv(FICHIER_POIDS)
    return horaire, poids


if __name__ == "__main__":
    horaire, poids = preparer()
    print(f"{len(horaire):,} heures, du {horaire.index.min()} au {horaire.index.max()} (UTC)")
    print("Poids régionaux (2016-2022) :")
    print((poids * 100).round(1).sort_values(ascending=False).to_string())
    print("Fichier :", FICHIER_SORTIE)
