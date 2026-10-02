"""Constantes communes du projet (protocole partagé)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

HEURE_DECISION = 14   # on prévoit à 14h le jour J
HORIZON = 24          # les 24 heures de J+1
TZ = "Europe/Paris"
