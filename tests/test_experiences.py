"""Tests de src/experiences.py (aucun calcul de modèle, aucun accès aux données)."""
import pandas as pd
import pytest

from src import experiences, features
from src import modeles_lineaires as m1


def test_lag_b_est_exactement_m1():
    for heure in range(24):
        assert experiences.VARIANTES_RETARDS["LAG-B"](heure) == m1.variables_retards_m1(heure)


def test_cal_d_est_exactement_m1():
    assert experiences.VARIANTES_CALENDRIER["CAL-D"] == m1.VARIABLES_CALENDRIER_BINAIRES_M1


def test_aucune_variante_n_utilise_la_veille_apres_12h():
    # La consommation de 13 h à 23 h du jour J n'est pas connue à 14 h.
    for retards in experiences.VARIANTES_RETARDS.values():
        for heure in range(13, 24):
            assert "conso_veille_effective_MW" not in retards(heure)


def test_la_variante_est_rendue_apres_le_calcul():
    avant_retards = m1.variables_retards_m1(5)
    avant_calendrier = list(m1.VARIABLES_CALENDRIER_BINAIRES_M1)

    with experiences.variante_m1(
        retards=experiences.VARIANTES_RETARDS["LAG-D"],
        calendrier=["ferie"],
    ):
        assert m1.variables_retards_m1(5) == ["conso_lag168_MW"]
        assert m1.variables_numeriques_m1(5) == ["conso_lag168_MW", "ferie"]

    assert m1.variables_retards_m1(5) == avant_retards
    assert m1.VARIABLES_CALENDRIER_BINAIRES_M1 == avant_calendrier


def test_dataset_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(features, "FICHIER_DATASET", tmp_path / "absent.csv")
    with pytest.raises(FileNotFoundError, match="src.features"):
        experiences.main([])


@pytest.mark.parametrize("options,test_lance", [([], False), (["--test-final"], True)])
def test_le_test_final_ne_se_lance_que_sur_demande(monkeypatch, tmp_path, options, test_lance):
    fichier = tmp_path / "dataset.csv"
    pd.DataFrame({"x": [1]}).to_csv(fichier, index=False)
    monkeypatch.setattr(features, "FICHIER_DATASET", fichier)

    appels = []
    for nom in ["ablation_retards_m1", "ablation_calendrier_m1", "ablation_m2",
                "selection_m3", "selection_m4", "test_final"]:
        monkeypatch.setattr(experiences, nom, lambda donnees, nom=nom: appels.append(nom))

    experiences.main(options)

    assert appels[:5] == ["ablation_retards_m1", "ablation_calendrier_m1", "ablation_m2",
                          "selection_m3", "selection_m4"]
    assert ("test_final" in appels) is test_lance
