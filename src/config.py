"""Décisions du groupe, centralisées en un seul endroit.

Règle :
Toute valeur modifiée ici doit également être documentée dans
docs/decisions.md. On ajoute une nouvelle décision sans effacer
l'ancienne, et la modification passe par une pull request relue
par l'autre membre du groupe.
"""

import datetime as dt
from pathlib import Path


# =============================================================================
# CHEMINS
# =============================================================================

RACINE = Path(__file__).resolve().parent.parent

# donnees-brutes : fichiers téléchargés, jamais modifiés à la main
# interim : fichiers intermédiaires (étapes de travail)
# donnees-preparees : fichiers propres, prêts pour les modèles
DATA_BRUTES = RACINE / "data" / "donnees-brutes"
DATA_INTERIM = RACINE / "data" / "interim"
DATA_PREPAREES = RACINE / "data" / "donnees-preparees"
# donnees-traitees : étapes de traitement de la météo (matrices, journaux,
# diagnostics). Non versionné : tout se reconstruit avec python -m src.pipeline_meteo
DATA_TRAITEES = RACINE / "data" / "donnees-traitees"
DOSSIER_METEO_BRUT = DATA_BRUTES / "meteo"
DOSSIER_METEO_TRAITE = DATA_TRAITEES / "meteo"

REPORT_TABLES = RACINE / "report" / "tables"
REPORT_FIGURES = RACINE / "report" / "figures"


# =============================================================================
# PROTOCOLE DE PRÉVISION
# =============================================================================

# Toutes les décisions opérationnelles sont exprimées par rapport
# à l'heure locale française.
FUSEAU = "Europe/Paris"

# La prévision est produite à 14 h le jour J.
HEURE_ORIGINE = 14

# Dernière consommation supposée connue à 14 h :
# valeur horaire étiquetée 12, correspondant à la tranche 12 h-13 h.
#
# Une valeur étiquetée 13 couvre la tranche 13 h-14 h et n'est donc
# pas considérée comme complètement disponible à 14 h.
DERNIERE_HEURE_CONSO_CONNUE = 12

# Pour la météo, on utilisera uniquement les observations dont
# l'heure locale est <= 13 h.
#
# Cette règle devra être vérifiée lors de l'étude détaillée de la
# disponibilité des données SYNOP.
DERNIERE_HEURE_METEO_LOCALE = 13

# À 14 h le jour J, les 24 heures du jour J+1 correspondent
# à des horizons allant de 10 h à 33 h.
HORIZON_MIN = 10
HORIZON_MAX = 33


# =============================================================================
# PÉRIODE ET DÉCOUPAGE TEMPOREL
# =============================================================================

# Les données sont chargées à partir du 1er décembre 2015.
# Décembre 2015 sert de marge historique pour construire certains
# retards avant le début de la période d'apprentissage.
DATA_DEBUT = dt.date(2015, 12, 1)
# Jusqu'au 2026-10-07 : 31 décembre 2025. Prolongé au 30 juin 2026 pour le test
# bonus (décision 3), une fois le test final 2024-2025 fait. Les traitements
# appris (météo, modèles) n'utilisent que 2016-2022 : ajouter 2026 ne change
# rien à 2016-2025 (vérifié, voir docs/decisions.md).
DATA_FIN = dt.date(2026, 6, 30)

# Années sur lesquelles la liste des stations SYNOP a été choisie (décision 7) :
# une station est gardée si elle est présente chaque année de 2015 à 2025. La
# liste est figée : les données de 2026 ne la modifient pas.
ANNEES_SELECTION_STATIONS = (2015, 2025)

# Découpage défini sur les jours cibles J+1.
#
# Important :
# - apprentissage : construction des modèles ;
# - validation : choix des variables, modèles et hyperparamètres ;
# - test : évaluation finale uniquement.
#
# Le test 2024-2025 ne doit pas être utilisé pour modifier les choix
# méthodologiques.
DECOUPAGE = {
    "apprentissage": (
        dt.date(2016, 1, 1),
        dt.date(2022, 12, 31),
    ),
    "validation": (
        dt.date(2023, 1, 1),
        dt.date(2023, 12, 31),
    ),
    "test": (
        dt.date(2024, 1, 1),
        dt.date(2025, 12, 31),
    ),
}

# Test bonus (décision 3) : janvier à juin 2026, données consolidées.
# Utilisé UNE SEULE FOIS, après le test final 2024-2025, résultats présentés à
# part (src/test_bonus.py). Il ne sert jamais à choisir ou régler quoi que ce
# soit : les configurations des modèles sont celles gelées pour 2024-2025.
TEST_BONUS = (
    dt.date(2026, 1, 1),
    dt.date(2026, 6, 30),
)


# =============================================================================
# PÉRIODE COVID
# =============================================================================

# Jours cibles retirés uniquement de l'apprentissage.
#
# Les valeurs observées pendant cette période restent disponibles
# comme historique pour calculer des retards.
#
# Cette décision devra faire l'objet d'une analyse de sensibilité
# sur la validation avant d'être considérée comme définitivement
# justifiée.
EXCLUSION_COVID = (
    dt.date(2020, 3, 17),
    dt.date(2020, 5, 17),
)


# =============================================================================
# RÉESTIMATION DES MODÈLES
# =============================================================================

# Réestimation mensuelle avec fenêtre croissante :
# chaque réestimation utilise uniquement les données disponibles
# antérieurement à l'origine concernée.
REESTIMATION = "mensuelle"


# =============================================================================
# MÉTÉO — SYNOP
# =============================================================================

# ---------------------------------------------------------------------------
# Sélection des stations
# ---------------------------------------------------------------------------
#
# ANCIENNE DÉCISION :
# 8 stations avaient initialement été retenues :
# Orly, Lyon-Saint-Exupéry, Marignane, Lille-Lesquin,
# Toulouse-Blagnac, Bordeaux-Mérignac, Strasbourg-Entzheim
# et Nantes-Bouguenais.
#
# NOUVELLE DÉCISION :
# ce choix n'est plus considéré comme définitif.
#
# Avant de fixer le nombre et la liste des stations, nous analyserons
# l'ensemble des stations métropolitaines disponibles afin d'étudier
# notamment :
#
# - leur couverture temporelle sur la période étudiée ;
# - les valeurs manquantes ;
# - les doublons éventuels ;
# - la stabilité de leur disponibilité selon les années ;
# - leur répartition géographique ;
# - la qualité générale des observations.
#
# Le nombre de stations sera donc déterminé après cette exploration
# et devra être justifié dans le rapport.
#
# Les codes OMM/WMO devront être conservés sous forme de chaînes
# de 5 caractères afin de préserver les zéros initiaux
# (par exemple "07149").
STATIONS_SYNOP = None


# ---------------------------------------------------------------------------
# Construction d'une information météorologique nationale
# ---------------------------------------------------------------------------
#
# ANCIENNE PISTE :
# moyenne simple des stations sélectionnées.
#
# NOUVELLE DÉCISION :
# aucune méthode d'agrégation n'est encore fixée.
#
# Après l'analyse des stations, différentes possibilités pourront être
# étudiées et justifiées, par exemple :
#
# - moyenne simple ;
# - pondération pertinente si elle est justifiée ;
# - autre représentation issue de l'analyse exploratoire.
#
# La décision finale sera prise avant l'évaluation sur le jeu de test.
TEMPERATURE_NATIONALE = None

# Réseau utilisé pour NETTOYER et IMPUTER : les 40 stations stables et
# métropolitaines (sélection automatique de src/meteo.py, Corse comprise).
#
# Stations utilisées pour la TEMPÉRATURE FRANCE : la consommation nationale RTE
# couvre la France continentale (elle est exactement la somme des 12 régions
# continentales, vérifié le 2026-10-05). Les stations corses sont donc exclues
# de la température France, mais restent dans le réseau d'imputation.
REGIONS_EXCLUES_TEMPERATURE_FRANCE = {"94"}  # code INSEE de la Corse

# Trois représentations candidates de la température France. Le choix se fera
# sur la validation 2023 uniquement (décision 8), jamais sur le test.
STATIONS_8_VILLES = {
    "Paris (Orly)": "07149",
    "Lyon (Saint-Exupéry)": "07481",
    "Marseille (Marignane)": "07650",
    "Lille (Lesquin)": "07015",
    "Toulouse (Blagnac)": "07630",
    "Bordeaux (Mérignac)": "07510",
    "Strasbourg (Entzheim)": "07190",
    "Nantes (Bouguenais)": "07222",
}
TEMPERATURE_FRANCE_CANDIDATES = ["temp_8_villes", "temp_38_simple", "temp_38_ponderee"]


# ---------------------------------------------------------------------------
# Paramètres appris sur les données : période d'apprentissage uniquement
# ---------------------------------------------------------------------------
#
# Toute quantité estimée sur les données météo (corrélations, voisins,
# régressions entre stations, choix d'une méthode d'imputation, poids
# régionaux, seuils d'anomalie) est apprise sur les observations antérieures
# à la fin de la période d'apprentissage (heure de Paris), jamais sur 2023-2025.
FIN_APPRENTISSAGE = DECOUPAGE["apprentissage"][1]  # 31 décembre 2022

# Règle de détection des observations aberrantes (appliquée automatiquement à
# toute la période, src/correction_anomalies_meteo.py). Une observation
# originale est déclarée aberrante si :
# - elle s'écarte de plus de SEUIL_ANOMALIE_SAUT_3H °C de la valeur de la même
#   station 3 h avant (uniquement le passé) ;
# - ET elle s'écarte de la valeur prédite au même instant par ses voisines de
#   plus que le plus grand écart observé sur la période d'apprentissage. Ce
#   second seuil est APPRIS par le code (environ 14 °C), pas fixé à la main.
SEUIL_ANOMALIE_SAUT_3H = 15.0


# ---------------------------------------------------------------------------
# Fréquence SYNOP
# ---------------------------------------------------------------------------
#
# Les fichiers SYNOP étudiés jusqu'ici indiquent généralement des
# observations toutes les 3 heures en UTC.
#
# Cette propriété sera contrôlée sur les données réellement récupérées
# pour les différentes années avant d'être considérée comme acquise
# pour l'ensemble de la période.
PAS_SYNOP_HEURES = 3


# ---------------------------------------------------------------------------
# Conversion de température
# ---------------------------------------------------------------------------

# Conversion Kelvin -> degrés Celsius :
#
# température_C = température_K - 273.15
KELVIN_VERS_CELSIUS = 273.15


# =============================================================================
# CONSOMMATION ÉLECTRIQUE
# =============================================================================

# Taille maximale actuellement envisagée pour l'interpolation
# de petits trous dans la série.
#
# Toute valeur interpolée devra être signalée explicitement
# (par exemple par une variable `interpole`).
#
# Cette règle reste à vérifier lors du traitement complet des données.
INTERPOLATION_MAX_HEURES = 3


# =============================================================================
# REPRODUCTIBILITÉ
# =============================================================================

# Graine commune pour les méthodes utilisant de l'aléatoire.
SEED = 42