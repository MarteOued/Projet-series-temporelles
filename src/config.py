"""Décisions du groupe, centralisées en un seul endroit.

Règle :
Toute valeur modifiée ici doit également être documentée dans
docs/decisions.md. On ajoute une nouvelle décision sans effacer
l'ancienne, et la modification passe par une pull request relue
par l'autre membre du groupe.
"""

import datetime as dt
import os
from pathlib import Path


# =============================================================================
# CHEMINS
# =============================================================================

RACINE = Path(__file__).resolve().parent.parent

# Mode « test bonus » (décision 3) : activé seulement par src/test_bonus.py, avec
# la variable d'environnement PROJET_TEST_BONUS=1. Les mêmes scripts traitent alors
# les données jusqu'au 30 juin 2026, mais écrivent dans des sous-dossiers
# « test_bonus » : les fichiers du projet (jusqu'au 31 décembre 2025) ne sont
# jamais modifiés.
MODE_TEST_BONUS = os.environ.get("PROJET_TEST_BONUS") == "1"
_SOUS_DOSSIER = "test_bonus" if MODE_TEST_BONUS else ""

# donnees-brutes : fichiers téléchargés, jamais modifiés à la main (communs aux deux modes)
# interim : fichiers intermédiaires (étapes de travail)
# donnees-preparees : fichiers propres, prêts pour les modèles
DATA_BRUTES = RACINE / "data" / "donnees-brutes"
DATA_PREPAREES_PROJET = RACINE / "data" / "donnees-preparees"
DATA_PREPAREES_BONUS = DATA_PREPAREES_PROJET / "test_bonus"
DATA_INTERIM = RACINE / "data" / "interim" / _SOUS_DOSSIER
DATA_PREPAREES = DATA_PREPAREES_BONUS if MODE_TEST_BONUS else DATA_PREPAREES_PROJET
# donnees-traitees : étapes de traitement de la météo (matrices, journaux,
# diagnostics). Non versionné : tout se reconstruit avec python -m src.pipeline_meteo
DATA_TRAITEES = RACINE / "data" / "donnees-traitees" / _SOUS_DOSSIER
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

# Pour la météo, on utilise uniquement les observations dont l'heure
# locale est <= 13 h (décision 6). Appliqué par protocole.limite_meteo_connue ;
# l'audit 2025 montre des observations publiées quelques minutes après leur heure.
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
# Fin des données du projet (décision 1). En mode test bonus seulement, les
# données vont jusqu'à la fin du test bonus (voir TEST_BONUS plus bas).
DATA_FIN_PROJET = dt.date(2025, 12, 31)

# Années sur lesquelles la liste des stations SYNOP a été choisie (décision 7) :
# une station est gardée si elle est présente chaque année de 2015 à 2025. La
# liste est figée : les données de 2026 du test bonus ne la modifient pas.
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

DATA_FIN = TEST_BONUS[1] if MODE_TEST_BONUS else DATA_FIN_PROJET


# =============================================================================
# PÉRIODE COVID
# =============================================================================

# Jours cibles retirés uniquement de l'apprentissage.
#
# Les valeurs observées pendant cette période restent disponibles
# comme historique pour calculer des retards.
#
# Analyse de sensibilité faite le 2026-10-07, après le gel des choix
# (data/resultats/sensibilite_covid_2023.csv) : garder ces jours aurait été
# meilleur sur 2023. La décision est maintenue, car le test avait déjà été vu
# (décision 9).
EXCLUSION_COVID = (
    dt.date(2020, 3, 17),
    dt.date(2020, 5, 17),
)


# =============================================================================
# RÉESTIMATION DES MODÈLES
# =============================================================================

# Réestimation avec fenêtre croissante (décision 4) : chaque mois sur le test
# 2024-2025 et le test bonus, chaque trimestre sur la validation 2023. Chaque
# bloc apprend uniquement sur les jours cibles antérieurs au bloc. Cette
# constante n'est lue que par les tests : les blocs sont définis dans
# src/modeles_lineaires.py.
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
# DÉCISION FINALE (décision 7) : 40 stations présentes chaque année de 2015 à
# 2025 et métropolitaines pour nettoyer et imputer ; les 38 stations
# continentales pour la température France. La liste est calculée par
# src/meteo.py ; cette constante n'est plus utilisée (gardée pour l'historique).
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
# DÉCISION FINALE (décision 8) : temp_38_ponderee, moyenne par région des 38
# stations continentales, pondérée par la consommation des régions. Choisie sur
# 2023, à égalité (moins de 1 MW) avec les deux autres candidates. Le candidat
# retenu est utilisé par src/modeles_meteo.py et src/analyses.py ; cette
# constante n'est plus utilisée (gardée pour l'historique).
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

# Taille maximale des trous comblés par interpolation (décision 10). Appliqué
# dans src/rte.py, avec la colonne `interpole` : 10 heures interpolées sur 10 ans,
# toutes à 2 h du matin le jour du passage à l'heure d'hiver.
INTERPOLATION_MAX_HEURES = 3


# =============================================================================
# REPRODUCTIBILITÉ
# =============================================================================

# Graine commune pour les méthodes utilisant de l'aléatoire.
SEED = 42