"""Benchmarks : des prévisions simples, SANS apprentissage, qui donnent le score à battre.

Un benchmark ne fait que recopier le passé de la consommation. Il n'a besoin ni de la
météo ni du calendrier : il peut donc être calculé dès que la consommation est prête.

Rappel du problème : à 14 h le jour J, on prévoit les 24 heures (heure de Paris) du
jour cible J+1.

- B1 « même jour, semaine précédente » : pour chaque heure H du jour cible, on recopie
  la consommation de l'heure H, 7 jours avant le jour cible (c'est le jour J-6).
- B2 « moyenne des 4 mêmes jours précédents » : moyenne de l'heure H, 7, 14, 21 et
  28 jours avant le jour cible. Plus stable que B1, car un jour bizarre pèse moins.

Les jours utilisés sont tous terminés bien avant 14 h le jour J : la fonction
`verifier_disponibilite` le contrôle avec la règle des 14 h de src/protocole.py.

Lancer depuis la racine du projet : python -m src.benchmarks
"""
import pandas as pd

from src import config, evaluation, protocole, rte

HEURES = list(range(24))
DECALAGE_B1 = [7]                 # en jours avant le jour cible
DECALAGES_B2 = [7, 14, 21, 28]


# --- La consommation rangée par jour et par heure de Paris -------------------
def consommation_par_jour(conso_h):
    """Range la consommation horaire en tableau : une ligne par jour, une colonne par heure.

    Les jours et les heures sont ceux de Paris, car le problème est posé en heure locale.
    Jours de changement d'heure :
    - jour de 23 h (mars) : l'heure 2 n'existe pas, sa case reste vide ;
    - jour de 25 h (octobre) : l'heure 2 existe deux fois, je fais la moyenne des deux.
    """
    paris = conso_h.index.tz_convert(config.FUSEAU)
    tableau = (
        pd.DataFrame({
            "date": pd.to_datetime(paris.date),
            "heure": paris.hour,
            "consommation_MW": conso_h["consommation_MW"].to_numpy(),
        })
        .pivot_table(index="date", columns="heure", values="consommation_MW", aggfunc="mean")
        .reindex(columns=HEURES)
    )
    tableau.columns.name = "heure"
    return tableau


def jours_changement_heure(conso_h):
    """Dates (Paris) qui ne comptent pas 24 heures : passages à l'heure d'été et d'hiver."""
    nb = rte.heures_par_jour(conso_h)
    return pd.to_datetime(nb[nb != 24].index)


# --- Les deux benchmarks -----------------------------------------------------
def moyenne_des_jours_precedents(conso_jour, jours_cibles, decalages):
    """Moyenne, heure par heure, des jours situés `decalages` jours avant chaque jour cible.

    Si une valeur manque pour un des jours (heure 2 d'un jour de 23 h), je fais la moyenne
    des valeurs disponibles. Si toutes manquent, la case reste vide.
    """
    jours_cibles = pd.DatetimeIndex(jours_cibles)
    copies = [
        conso_jour.reindex(jours_cibles - pd.Timedelta(days=d)).set_axis(jours_cibles)
        for d in decalages
    ]
    return pd.concat(copies).groupby(level=0).mean().reindex(jours_cibles)


def benchmark_b1(conso_jour, jours_cibles):
    """B1 : le même jour de la semaine précédente (7 jours avant le jour cible)."""
    return moyenne_des_jours_precedents(conso_jour, jours_cibles, DECALAGE_B1)


def benchmark_b2(conso_jour, jours_cibles):
    """B2 : moyenne des 4 mêmes jours de la semaine précédents (7, 14, 21, 28 jours avant)."""
    return moyenne_des_jours_precedents(conso_jour, jours_cibles, DECALAGES_B2)


# --- La règle des 14 h -------------------------------------------------------
def verifier_disponibilite(jours_cibles, decalages):
    """Vérifie qu'aucun benchmark n'utilise une heure inconnue à 14 h le jour J.

    Pour chaque jour cible, la prévision est faite la veille (jour J). Le jour le plus récent
    utilisé est `min(decalages)` jours avant le jour cible ; sa dernière heure (23 h-24 h,
    heure de Paris) doit être terminée avant la fin des données connues à 14 h le jour J.
    S'arrête avec une erreur sinon.
    """
    plus_recent = min(decalages)
    for jour_cible in pd.DatetimeIndex(jours_cibles):
        jour_J = jour_cible - pd.Timedelta(days=1)
        jour_utilise = jour_cible - pd.Timedelta(days=plus_recent)
        derniere_heure = pd.Timestamp(f"{jour_utilise:%Y-%m-%d} 23:00", tz=config.FUSEAU)
        if not protocole.est_connue_a_14h(derniere_heure.tz_convert("UTC"), jour_J):
            raise ValueError(f"Fuite : la prévision du {jour_cible:%Y-%m-%d} utilise le "
                             f"{jour_utilise:%Y-%m-%d}, inconnu à 14 h le {jour_J:%Y-%m-%d}")


# --- Tout calculer pour une période ------------------------------------------
def jours_de_la_periode(nom_periode):
    """Les jours cibles d'une période du découpage (config.DECOUPAGE)."""
    debut, fin = config.DECOUPAGE[nom_periode]
    return pd.date_range(debut, fin, freq="D")


def evaluer_periode(nom_periode, conso_h=None):
    """Calcule B1 et B2 sur une période et renvoie (tableau de scores, vraies valeurs, prévisions).

    Les jours de changement d'heure sont retirés de la notation (piste de la décision 11) :
    ils n'ont pas 24 heures, on ne peut donc pas les comparer heure par heure.
    """
    if nom_periode == "test":
        raise ValueError("Le test 2024-2025 ne s'utilise qu'une fois, à la fin, après gel des choix.")

    conso_h = rte.lire_prepare() if conso_h is None else conso_h
    conso_jour = consommation_par_jour(conso_h)
    jours = jours_de_la_periode(nom_periode)
    jours = jours[~jours.isin(jours_changement_heure(conso_h))]

    verifier_disponibilite(jours, DECALAGE_B1)
    verifier_disponibilite(jours, DECALAGES_B2)

    reel = conso_jour.reindex(jours)
    previsions = {
        "B1 : semaine précédente": benchmark_b1(conso_jour, jours),
        "B2 : moyenne de 4 semaines": benchmark_b2(conso_jour, jours),
    }
    return evaluation.comparer(reel, previsions), reel, previsions


if __name__ == "__main__":
    pd.set_option("display.width", 120)
    for periode in ["apprentissage", "validation"]:
        scores, _, _ = evaluer_periode(periode)
        print(f"\n=== {periode} ===")
        print(scores.round(1).to_string())
