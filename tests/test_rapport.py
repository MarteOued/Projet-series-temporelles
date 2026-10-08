"""Tests de src/rapport.py (mise en forme seulement : aucun modèle n'est calculé)."""
import pandas as pd

from src import rapport


def test_tableau_markdown_a_la_francaise():
    t = pd.DataFrame({"Méthode": ["M2"], "MAE (MW)": [1330.6], "MAPE (%)": [2.57]})
    texte = rapport.en_markdown(t, {"MAPE (%)": 1})
    assert "| M2 | 1 331 | 2,6 |" in texte
    assert texte.splitlines()[1] == "|---|---:|---:|"


def test_categorie_des_pires_jours():
    redoux = {"MAE_MW": 8000, "MAE_Plafond_MW": 900, "type_jour": "week-end"}
    noel = {"MAE_MW": 7000, "MAE_Plafond_MW": 5600, "type_jour": "Noël"}
    autre = {"MAE_MW": 6000, "MAE_Plafond_MW": 5000, "type_jour": "ouvré"}
    assert rapport.categorie_enonce(redoux).startswith("Limite des données")
    assert rapport.categorie_enonce(noel).startswith("Limite du modèle")
    assert rapport.categorie_enonce(autre).startswith("Non classé")
