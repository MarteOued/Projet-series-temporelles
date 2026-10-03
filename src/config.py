"""Décisions du groupe, en un seul endroit.

Règle : toute valeur modifiée ici est aussi notée dans docs/decisions.md
(on ajoute une ligne, on n'efface pas l'ancienne) et passe par une pull request
relue par l'autre personne.
"""
import datetime as dt
from pathlib import Path

# --- Chemins -----------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
# donnees-brutes : fichiers téléchargés, jamais modifiés à la main
# interim : fichiers intermédiaires (étapes de travail)
# donnees-preparees : fichiers propres, prêts pour les modèles
DATA_BRUTES = RACINE / "data" / "donnees-brutes"
DATA_INTERIM = RACINE / "data" / "interim"
DATA_PREPAREES = RACINE / "data" / "donnees-preparees"
REPORT_TABLES = RACINE / "report" / "tables"
REPORT_FIGURES = RACINE / "report" / "figures"

# --- Protocole de prévision --------------------------------------------------
FUSEAU = "Europe/Paris"
HEURE_ORIGINE = 14  # la prévision est produite à 14 h (heure de Paris) le jour J

# Dernière consommation supposée connue à 14 h : la valeur horaire étiquetée 12,
# c'est-à-dire la tranche 12 h-13 h. Une valeur étiquetée 13 couvre 13 h-14 h et
# n'est pas complète à 14 h. Pour la météo : dernière observation dont l'heure
# locale est <= 13 h.
DERNIERE_HEURE_CONSO_CONNUE = 12
DERNIERE_HEURE_METEO_LOCALE = 13

# Horizons (en heures après l'origine) des 24 heures de J+1 : de 10 à 33.
HORIZON_MIN = 10
HORIZON_MAX = 33

# --- Période et découpage (jours cibles J+1) ---------------------------------
# Les données sont chargées dès le 1er décembre 2015 : ce mois sert de marge
# pour calculer les retards (jusqu'à 28 jours).
DATA_DEBUT = dt.date(2015, 12, 1)
DATA_FIN = dt.date(2025, 12, 31)

DECOUPAGE = {
    "apprentissage": (dt.date(2016, 1, 1), dt.date(2022, 12, 31)),
    "validation": (dt.date(2023, 1, 1), dt.date(2023, 12, 31)),
    "test": (dt.date(2024, 1, 1), dt.date(2025, 12, 31)),
}

# Jours cibles retirés de l'APPRENTISSAGE seulement (premier confinement, plus une
# semaine pour que le retard de 168 h ne pointe pas sur des jours de confinement).
# Leurs valeurs restent utilisables comme retards. Jamais en validation ni en test.
EXCLUSION_COVID = (dt.date(2020, 3, 17), dt.date(2020, 5, 17))

REESTIMATION = "mensuelle"  # fenêtre qui grandit, données antérieures seulement

# --- Météo -------------------------------------------------------------------
# Codes OMM (texte de 5 caractères, avec le zéro initial) : c'est le format de la
# colonne geo_id_wmo des fichiers SYNOP. La liste des stations donne l'ID en entier
# (7149) : passer par str(id).zfill(5).
STATIONS_SYNOP = {
    "Paris (Orly)": "07149",
    "Lyon (Saint-Exupéry)": "07481",
    "Marseille (Marignane)": "07650",
    "Lille (Lesquin)": "07015",
    "Toulouse (Blagnac)": "07630",
    "Bordeaux (Mérignac)": "07510",
    "Strasbourg (Entzheim)": "07190",
    "Nantes (Bouguenais)": "07222",
}

TEMPERATURE_NATIONALE = "moyenne_simple"  # à comparer à "ponderee_population"
PAS_SYNOP_HEURES = 3  # observations toutes les 3 heures, en UTC
KELVIN_VERS_CELSIUS = 273.15

# --- Consommation ------------------------------------------------------------
INTERPOLATION_MAX_HEURES = 3  # petits trous seulement, signalés (colonne `interpole`)

SEED = 42
