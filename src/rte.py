"""Consommation électrique RTE : téléchargement, nettoyage et passage à l'heure.

Lancer tout le pipeline depuis la racine du projet :

    python -m src.rte

Étapes (les mêmes que dans notebooks/01_donnees_RTE.ipynb, qui les explique en détail) :
1. télécharger tout le jeu éCO2mix national, tel que RTE le publie (donnees-brutes) ;
2. garder la consommation et la période d'étude ;
3. enlever les lignes fantômes des jours de passage à l'heure d'été ;
4. placer les données sur une grille UTC complète (les trous deviennent visibles) ;
5. faire la moyenne des deux demi-heures de chaque heure ;
6. combler les trous de 3 heures ou moins (colonne `interpole`) ;
7. contrôler le résultat, puis le sauvegarder (donnees-preparees).
"""
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from src import config

# --- Fichiers ----------------------------------------------------------------
URL_EXPORT = (
    "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "eco2mix-national-cons-def/exports/csv"
)
FICHIER_BRUT = config.DATA_BRUTES / "rte" / "eco2mix_national_complet.csv"
FICHIER_INTERIM = config.DATA_INTERIM / "rte" / "conso_30min_utc.csv"
FICHIER_PREPARE = config.DATA_PREPAREES / "rte" / "conso_horaire_utc.csv"

# Les colonnes que je garde : la consommation et ses repères. Les 31 autres colonnes
# d'éCO2mix (production, échanges, CO2, prévisions de RTE) sont interdites comme variables.
COLONNES_GARDEES = ["perimetre", "nature", "date", "heure", "date_heure", "consommation"]

# Valeurs plausibles pour la consommation horaire de la France (en MW)
CONSO_MIN_MW, CONSO_MAX_MW = 25_000, 100_000


# --- 1. Téléchargement -------------------------------------------------------
def telecharger(forcer=False):
    """Télécharge tout le jeu éCO2mix national (toutes les dates, toutes les colonnes).

    Le fichier n'est téléchargé qu'une fois : s'il existe déjà, je le garde,
    sauf si `forcer=True`.
    """
    if FICHIER_BRUT.exists() and not forcer:
        return FICHIER_BRUT

    parametres = {
        "order_by": "date_heure",  # les lignes dans l'ordre du temps
        "timezone": "UTC",         # date_heure en UTC : pas d'heure en double ou manquante
        "delimiter": ";",
    }
    reponse = requests.get(URL_EXPORT, params=parametres, timeout=1800)
    reponse.raise_for_status()  # erreur claire si le serveur répond mal
    FICHIER_BRUT.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_BRUT.write_bytes(reponse.content)
    return FICHIER_BRUT


def lire_brut(chemin=FICHIER_BRUT):
    """Lit le fichier brut tel quel (37 colonnes, une ligne par quart d'heure)."""
    # "utf-8-sig" enlève le caractère invisible (BOM) que l'API met au début du fichier
    return pd.read_csv(chemin, sep=";", encoding="utf-8-sig", low_memory=False)


# --- 2. Sélection ------------------------------------------------------------
def selectionner(brut, debut=config.DATA_DEBUT, fin=config.DATA_FIN):
    """Garde la consommation de la France, de `debut` à `fin` (dates de Paris, incluses).

    - Colonnes : la consommation et ses repères (voir COLONNES_GARDEES).
    - Période : par défaut du 1er décembre 2015 au 31 décembre 2025. Décembre 2015 sert
      seulement de marge pour calculer les retards (jusqu'à 28 jours) des premiers jours de 2016.
    - Lignes : celles où la consommation est remplie (les lignes :15 et :45 sont toujours vides).
    """
    conso = brut[COLONNES_GARDEES]
    # La colonne "date" est un texte "AAAA-MM-JJ" : comparer ces textes revient à comparer les dates
    dans_la_periode = (conso["date"] >= str(debut)) & (conso["date"] <= str(fin))
    garder = dans_la_periode & (conso["perimetre"] == "France") & conso["consommation"].notna()
    return conso.loc[garder].drop(columns="perimetre").copy()


# --- 3. Nettoyage ------------------------------------------------------------
def lignes_fantomes(conso):
    """Repère les lignes dont l'heure écrite par RTE ne correspond pas à leur instant UTC.

    Le jour du passage à l'heure d'été, l'heure locale « 02:00 » n'existe pas. RTE fournit
    pourtant des lignes « 02:00 » et « 02:30 » : ce sont des copies, qui tombent sur le même
    instant UTC que « 03:00 » et « 03:30 ». Je recalcule l'heure de Paris à partir de l'instant
    UTC : si elle diffère de la date et de l'heure écrites par RTE, la ligne est fantôme.
    """
    heure_paris = pd.to_datetime(conso["date_heure"], utc=True).dt.tz_convert(config.FUSEAU)
    date_recalculee = heure_paris.dt.strftime("%Y-%m-%d")
    heure_recalculee = heure_paris.dt.strftime("%H:%M")
    return (date_recalculee != conso["date"]) | (heure_recalculee != conso["heure"])


def nettoyer(conso):
    """Enlève les lignes fantômes et renvoie la consommation à 30 minutes, indexée en UTC."""
    propre = conso.loc[~lignes_fantomes(conso)].copy()
    propre["date_heure_utc"] = pd.to_datetime(propre["date_heure"], utc=True)
    propre["consommation"] = pd.to_numeric(propre["consommation"], errors="raise")

    if propre["date_heure_utc"].duplicated().any():
        raise ValueError("Il reste plusieurs lignes pour un même instant UTC après nettoyage")

    return (
        propre.set_index("date_heure_utc")[["consommation", "nature"]]
        .rename(columns={"consommation": "consommation_MW"})
        .sort_index()
    )


# --- 4. Dates et heures ------------------------------------------------------
def grille_30min(debut=config.DATA_DEBUT, fin=config.DATA_FIN):
    """Toutes les demi-heures de `debut` 0 h à `fin` 23 h 30 (heure de Paris), en UTC."""
    debut_utc = pd.Timestamp(debut, tz=config.FUSEAU).tz_convert("UTC")
    fin_utc = (pd.Timestamp(fin + dt.timedelta(days=1), tz=config.FUSEAU)
               - pd.Timedelta(minutes=30)).tz_convert("UTC")
    return pd.date_range(debut_utc, fin_utc, freq="30min", name="date_heure_utc")


def mettre_sur_grille(conso_30min, debut=config.DATA_DEBUT, fin=config.DATA_FIN):
    """Place les données sur la grille complète : une demi-heure absente devient une valeur vide."""
    grille = grille_30min(debut, fin)
    if not conso_30min.index.isin(grille).all():
        raise ValueError("Des données tombent en dehors de la grille des demi-heures")
    return conso_30min.reindex(grille)


# --- 5. Passage à l'heure ----------------------------------------------------
def agreger_a_l_heure(conso_30min):
    """Moyenne des deux demi-heures de chaque heure.

    La moyenne et pas la somme : la consommation est une puissance (MW), pas une énergie.
    La valeur étiquetée H couvre la tranche [H, H+1[. Si les deux demi-heures manquent,
    l'heure reste vide.
    """
    conso_h = conso_30min[["consommation_MW"]].resample("1h").mean()
    conso_h["nature"] = conso_30min["nature"].resample("1h").first()
    return conso_h


# --- 6. Valeurs manquantes ---------------------------------------------------
def longueur_des_trous(serie):
    """Pour chaque valeur vide, la longueur du trou auquel elle appartient (0 si remplie)."""
    vide = serie.isna()
    # Je numérote les blocs consécutifs : le numéro change à chaque passage vide <-> rempli
    numero_bloc = (vide != vide.shift()).cumsum()
    return vide.groupby(numero_bloc).transform("sum").where(vide, 0).astype(int)


def combler_les_trous(conso_h, max_heures=config.INTERPOLATION_MAX_HEURES):
    """Interpole linéairement les trous de `max_heures` heures ou moins.

    Attention : interpolate(limit=3) remplirait aussi les 3 premières heures d'un trou de
    5 heures. Je mesure donc d'abord la longueur de chaque trou. Les heures comblées sont
    marquées dans la colonne `interpole`.
    """
    resultat = conso_h.copy()
    longueur = longueur_des_trous(resultat["consommation_MW"])
    a_combler = (longueur > 0) & (longueur <= max_heures)

    interpolee = resultat["consommation_MW"].interpolate(method="time", limit_area="inside")
    resultat.loc[a_combler, "consommation_MW"] = interpolee[a_combler]
    resultat["interpole"] = a_combler
    resultat["nature"] = resultat["nature"].ffill()  # même version que l'heure d'avant
    return resultat


# --- 7. Contrôles et sauvegarde ----------------------------------------------
def heures_par_jour(conso_h):
    """Nombre d'heures de chaque jour, en heure de Paris (24, ou 23 / 25 aux changements d'heure)."""
    jours = conso_h.index.tz_convert(config.FUSEAU).date
    return pd.Series(1, index=jours).groupby(level=0).sum()


def controler(conso_h):
    """Vérifie ce qui doit être vrai. S'arrête avec une erreur claire sinon."""
    serie = conso_h["consommation_MW"]

    if not conso_h.index.is_unique:
        raise ValueError("Des heures sont en double")
    if not (conso_h.index.to_series().diff().dropna() == pd.Timedelta("1h")).all():
        raise ValueError("La grille horaire n'est pas régulière")
    if serie.isna().any():
        raise ValueError(f"{serie.isna().sum()} heures sont encore vides")
    if not serie.between(CONSO_MIN_MW, CONSO_MAX_MW).all():
        raise ValueError("Des valeurs sont hors de la plage plausible")

    # 24 heures par jour, sauf 23 h le dernier dimanche de mars et 25 h le dernier d'octobre
    for jour, nb in heures_par_jour(conso_h).items():
        attendu = 24
        if jour.weekday() == 6 and jour.month == 3 and jour.day >= 25:
            attendu = 23
        if jour.weekday() == 6 and jour.month == 10 and jour.day >= 25:
            attendu = 25
        if nb != attendu:
            raise ValueError(f"Le {jour} compte {nb} heures au lieu de {attendu}")


def sauvegarder(conso_h, chemin=FICHIER_PREPARE):
    """Sauvegarde le fichier final : date_heure_utc (index), consommation_MW, interpole, nature."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conso_h[["consommation_MW", "interpole", "nature"]].to_csv(chemin)
    return chemin


def lire_prepare(chemin=FICHIER_PREPARE):
    """Relit le fichier final, avec l'index en UTC."""
    return pd.read_csv(chemin, index_col="date_heure_utc", parse_dates=["date_heure_utc"])


# --- Tout le pipeline --------------------------------------------------------
def preparer(forcer_telechargement=False):
    """Enchaîne toutes les étapes et sauvegarde le fichier final. Renvoie la série horaire."""
    brut = lire_brut(telecharger(forcer=forcer_telechargement))
    conso_30min = mettre_sur_grille(nettoyer(selectionner(brut)))

    FICHIER_INTERIM.parent.mkdir(parents=True, exist_ok=True)
    conso_30min.to_csv(FICHIER_INTERIM)

    conso_h = combler_les_trous(agreger_a_l_heure(conso_30min))
    controler(conso_h)
    sauvegarder(conso_h)
    return conso_h


if __name__ == "__main__":
    resultat = preparer()
    print(f"{len(resultat):,} heures, du {resultat.index[0]} au {resultat.index[-1]} (UTC)")
    print(f"Heures interpolées : {resultat['interpole'].sum()}")
    print("Fichier :", FICHIER_PREPARE)
