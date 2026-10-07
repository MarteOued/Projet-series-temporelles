"""Le tableau de bord : chaque page s'affiche sans erreur, et les chiffres sont ceux du rapport."""
from pathlib import Path

import pandas as pd
import pytest

from src import visualisation as vis

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "data" / "resultats" / "visualisation_previsions.csv"

pytestmark = pytest.mark.skipif(not FICHIER.exists(), reason="lancer d'abord python -m src.visualisation")

PAGES = ["page_accueil", "page_methode", "page_donnees", "page_modeles", "page_jour", "page_classement",
         "page_echecs", "page_biais", "page_choix", "page_limites", "page_reproduire", "page_lexique"]


def lancer_page(nom_page, racine):
    import importlib.util
    import sys

    sys.path.insert(0, racine)
    spec = importlib.util.spec_from_file_location("tableau_de_bord", f"{racine}/app/tableau_de_bord.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    getattr(module, nom_page)()


@pytest.mark.parametrize("nom_page", PAGES)
def test_chaque_page_s_affiche_sans_erreur(nom_page):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_function(lancer_page, args=(nom_page, str(RACINE)), default_timeout=120)
    app.run()
    assert not app.exception, app.exception


@pytest.mark.parametrize("periode,fichier", [
    ("validation", "comparaison_validation_2023"),
    ("test", "comparaison_test_2024_2025"),
    ("test_bonus", "test_bonus_2026_comparaison"),
])
def test_memes_scores_que_les_comparaisons(periode, fichier):
    previsions = pd.read_csv(FICHIER)
    scores = vis.scores(previsions[previsions["periode"] == periode])
    reference = pd.read_csv(RACINE / "data" / "resultats" / f"{fichier}.csv").set_index("methode")
    reference.index = reference.index.map(vis.NOMS_COURTS)
    for methode in vis.METHODES:
        assert scores.loc[methode, "nb_jours"] == reference.loc[methode, "nb_jours"]
        # le fichier du tableau de bord arrondit les MW au dixième
        assert scores.loc[methode, "MAE (MW)"] == pytest.approx(reference.loc[methode, "MAE (MW)"], abs=0.1)


def test_tableau_jour_heure():
    previsions = pd.DataFrame({
        "periode": "test", "jour_cible": ["2024-01-02"] * 24, "heure": range(24),
        "reel_MW": 50_000.0, **{m: 50_100.0 for m in vis.METHODES},
    })
    erreurs = vis.erreurs_quotidiennes(previsions, "M2")
    assert erreurs["mae"].iloc[0] == pytest.approx(100.0)
    assert erreurs["biais"].iloc[0] == pytest.approx(100.0)
