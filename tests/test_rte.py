"""Tests de src/rte.py sur de fausses données qui imitent RTE (aucun accès réseau)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src import rte

# Deux week-ends avec changement d'heure en 2021 : passage à l'heure d'été le dimanche
# 28 mars, passage à l'heure d'hiver le dimanche 31 octobre.
JOURS_MARS = (dt.date(2021, 3, 27), dt.date(2021, 3, 29))
JOURS_OCTOBRE = (dt.date(2021, 10, 30), dt.date(2021, 11, 1))


def faux_brut(debut, fin):
    """Fabrique un faux fichier RTE, construit comme le vrai.

    - 96 lignes par jour (une par quart d'heure d'horloge, "00:00" à "23:45"), même les
      jours de changement d'heure ;
    - consommation remplie seulement à :00 et :30 ;
    - le jour de l'heure d'été, "02:00" (qui n'existe pas) tombe sur le même instant UTC
      que "03:00" : ce sont les lignes fantômes ;
    - le jour de l'heure d'hiver, "02:00" n'apparaît qu'une fois (la deuxième) : il manque
      donc une heure en UTC.
    """
    lignes = []
    for jour in pd.date_range(debut, fin, freq="D"):
        for quart in range(96):
            heure = f"{quart // 4:02d}:{(quart % 4) * 15:02d}"
            local = pd.Timestamp(f"{jour:%Y-%m-%d} {heure}").tz_localize(
                "Europe/Paris", nonexistent="shift_forward", ambiguous=False)
            minute = quart % 4 * 15
            lignes.append({
                "perimetre": "France",
                "nature": "Données définitives",
                "date": f"{jour:%Y-%m-%d}",
                "heure": heure,
                "date_heure": local.tz_convert("UTC").isoformat(),
                # une valeur différente pour chaque ligne, pour suivre les calculs
                "consommation": 50_000 + quart * 10 if minute in (0, 30) else np.nan,
                "nucleaire": 40_000,  # une colonne interdite, qui doit disparaître
            })
    return pd.DataFrame(lignes)


def pipeline(debut, fin):
    conso_30min = rte.mettre_sur_grille(rte.nettoyer(rte.selectionner(faux_brut(debut, fin), debut, fin)),
                                        debut, fin)
    return conso_30min, rte.combler_les_trous(rte.agreger_a_l_heure(conso_30min))


def test_selection_garde_la_consommation_et_la_periode():
    brut = faux_brut(*JOURS_MARS)
    conso = rte.selectionner(brut, dt.date(2021, 3, 28), dt.date(2021, 3, 28))
    assert list(conso.columns) == ["nature", "date", "heure", "date_heure", "consommation"]
    assert set(conso["date"]) == {"2021-03-28"}
    assert conso["consommation"].notna().all()           # plus de lignes :15 et :45
    assert set(conso["heure"].str[-2:]) == {"00", "30"}


def test_lignes_fantomes_du_passage_a_l_heure_d_ete():
    conso = rte.selectionner(faux_brut(*JOURS_MARS), *JOURS_MARS)
    fantomes = conso[rte.lignes_fantomes(conso)]
    assert list(fantomes["date"]) == ["2021-03-28", "2021-03-28"]
    assert list(fantomes["heure"]) == ["02:00", "02:30"]
    # après nettoyage, plus aucun instant UTC en double
    assert rte.nettoyer(conso).index.is_unique


def test_heure_manquante_du_passage_a_l_heure_d_hiver():
    conso_30min, _ = pipeline(*JOURS_OCTOBRE)
    trous = conso_30min.index[conso_30min["consommation_MW"].isna()]
    # la première heure "2 h" du 31 octobre (2 h-3 h en heure d'été) n'est pas fournie par RTE
    assert list(trous.tz_convert("Europe/Paris").strftime("%Y-%m-%d %H:%M %z")) == [
        "2021-10-31 02:00 +0200", "2021-10-31 02:30 +0200"]


def test_moyenne_des_deux_demi_heures():
    conso_30min = pd.DataFrame(
        {"consommation_MW": [60_000.0, 62_000.0], "nature": ["Données définitives"] * 2},
        index=pd.date_range("2021-01-04 17:00", periods=2, freq="30min", tz="UTC"),
    )
    conso_h = rte.agreger_a_l_heure(conso_30min)
    assert len(conso_h) == 1
    assert conso_h["consommation_MW"].iloc[0] == 61_000  # la moyenne, pas la somme


def test_seuls_les_trous_courts_sont_combles():
    index = pd.date_range("2021-01-04", periods=12, freq="h", tz="UTC")
    valeurs = [1.0, np.nan, np.nan, 4.0, 5.0, np.nan, np.nan, np.nan, np.nan, np.nan, 11.0, 12.0]
    conso_h = pd.DataFrame({"consommation_MW": valeurs, "nature": "Données définitives"}, index=index)

    assert list(rte.longueur_des_trous(conso_h["consommation_MW"])) == [0, 2, 2, 0, 0, 5, 5, 5, 5, 5, 0, 0]

    resultat = rte.combler_les_trous(conso_h, max_heures=3)
    assert list(resultat["consommation_MW"].iloc[1:3]) == [2.0, 3.0]   # trou de 2 h : comblé
    assert resultat["consommation_MW"].iloc[5:10].isna().all()         # trou de 5 h : laissé vide
    assert list(resultat["interpole"]) == [False, True, True] + [False] * 9


def test_pipeline_complet_sur_les_deux_changements_d_heure():
    for debut, fin in [JOURS_MARS, JOURS_OCTOBRE]:
        _, conso_h = pipeline(debut, fin)
        rte.controler(conso_h)  # ne doit pas lever d'erreur
        assert sorted(rte.heures_par_jour(conso_h).values) in ([23, 24, 24], [24, 24, 25])
    _, conso_h = pipeline(*JOURS_OCTOBRE)
    assert conso_h["interpole"].sum() == 1  # l'heure manquante d'octobre a été comblée


def test_controle_detecte_une_heure_vide():
    _, conso_h = pipeline(*JOURS_MARS)
    conso_h.iloc[10, conso_h.columns.get_loc("consommation_MW")] = np.nan
    with pytest.raises(ValueError, match="vides"):
        rte.controler(conso_h)


def test_controle_detecte_une_valeur_impossible():
    _, conso_h = pipeline(*JOURS_MARS)
    conso_h.iloc[10, conso_h.columns.get_loc("consommation_MW")] = 500_000
    with pytest.raises(ValueError, match="plausible"):
        rte.controler(conso_h)
