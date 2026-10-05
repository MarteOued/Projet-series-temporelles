"""Benchmarks : des prévisions simples, SANS apprentissage, qui donnent le score à battre.

Un benchmark ne fait que recopier le passé de la consommation. Il n'a besoin ni de la
météo ni du calendrier : il peut donc être calculé dès que la consommation est prête.

Rappel du problème : à 14 h le jour J, on prévoit les 24 heures (heure de Paris) du
jour cible J+1.

- B0 « veille effective » : « demain ressemblera à aujourd'hui », mais en respectant la
  règle des 14 h. À 14 h le jour J, on ne connaît le jour J que jusqu'à la tranche 12 h-13 h.
  Pour les heures 0 à 12 du jour cible, je recopie donc la même heure du jour J (1 jour
  avant) ; pour les heures 13 à 23, la même heure du jour J-1 (2 jours avant).
- B1 « même jour, semaine précédente » : pour chaque heure H du jour cible, on recopie
  la consommation de l'heure H, 7 jours avant le jour cible (c'est le jour J-6).
- B2 « moyenne des 4 mêmes jours précédents » : moyenne de l'heure H, 7, 14, 21 et
  28 jours avant le jour cible. Plus stable que B1, car un jour bizarre pèse moins.

Pour chaque benchmark, la fonction `verifier_disponibilite` contrôle, heure par heure,
qu'aucune valeur utilisée n'est inconnue à 14 h (règle de src/protocole.py).

Lancer depuis la racine du projet : python -m src.benchmarks
"""
import pandas as pd

from src import config, evaluation, protocole, rte

HEURES = list(range(24))

# Pour chaque heure H du jour cible : de combien de jours je recule pour recopier l'heure H.
DECALAGES_B0 = {
    H: [1] if H <= config.DERNIERE_HEURE_CONSO_CONNUE else [2]  # 1 jour = jour J, 2 jours = J-1
    for H in HEURES
}
DECALAGE_B1 = [7]                 # la même liste pour toutes les heures
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
def _par_heure(decalages):
    """Accepte une liste commune à toutes les heures, ou un dict {heure: liste}."""
    if isinstance(decalages, dict):
        return decalages
    return {H: list(decalages) for H in HEURES}


def moyenne_des_jours_precedents(conso_jour, jours_cibles, decalages):
    """Pour chaque heure H, moyenne de l'heure H des jours situés `decalages` jours avant.

    `decalages` est une liste (la même pour toutes les heures, ex. [7]) ou un dict
    {heure: liste} quand le recul dépend de l'heure (B0).
    Si une valeur manque pour un des jours (heure 2 d'un jour de 23 h), je fais la moyenne
    des valeurs disponibles. Si toutes manquent, la case reste vide.
    """
    jours_cibles = pd.DatetimeIndex(jours_cibles)
    prevision = pd.DataFrame(index=jours_cibles, columns=HEURES, dtype=float)
    prevision.columns.name = "heure"
    for heure, liste in _par_heure(decalages).items():
        copies = pd.concat(
            [conso_jour[heure].reindex(jours_cibles - pd.Timedelta(days=d)).set_axis(jours_cibles)
             for d in liste],
            axis=1,
        )
        prevision[heure] = copies.mean(axis=1)
    return prevision


def benchmark_b0(conso_jour, jours_cibles):
    """B0 : la veille effective (jour J pour les heures 0 à 12, jour J-1 pour 13 à 23)."""
    return moyenne_des_jours_precedents(conso_jour, jours_cibles, DECALAGES_B0)


def benchmark_b1(conso_jour, jours_cibles):
    """B1 : le même jour de la semaine précédente (7 jours avant le jour cible)."""
    return moyenne_des_jours_precedents(conso_jour, jours_cibles, DECALAGE_B1)


def benchmark_b2(conso_jour, jours_cibles):
    """B2 : moyenne des 4 mêmes jours de la semaine précédents (7, 14, 21, 28 jours avant)."""
    return moyenne_des_jours_precedents(conso_jour, jours_cibles, DECALAGES_B2)


# --- La règle des 14 h -------------------------------------------------------
def verifier_disponibilite(jours_cibles, decalages):
    """Vérifie, heure par heure, qu'aucun benchmark n'utilise une valeur inconnue à 14 h le jour J.

    Pour le jour cible et l'heure H, la prévision est faite la veille (jour J). La valeur
    recopiée la plus récente est l'heure H, `min(decalages[H])` jours avant le jour cible.
    Cette heure doit être terminée avant la fin des données connues à 14 h le jour J
    (src/protocole.py). S'arrête avec une erreur sinon.
    """
    jours_cibles = pd.DatetimeIndex(jours_cibles)
    # Fin des données connues à 14 h le jour J (= veille du jour cible), en UTC
    limites = pd.DatetimeIndex(
        [protocole.fin_des_donnees_connues(j) for j in jours_cibles - pd.Timedelta(days=1)]
    )
    for heure, liste in _par_heure(decalages).items():
        recul = min(liste)
        # Début de l'heure recopiée, en heure de Paris puis en UTC. Les heures qui n'existent
        # pas ou existent deux fois (changement d'heure) sont prises au plus tard : prudent.
        debut = (jours_cibles - pd.Timedelta(days=recul) + pd.Timedelta(hours=heure)).tz_localize(
            config.FUSEAU, nonexistent="shift_forward", ambiguous=False
        ).tz_convert("UTC")
        fuite = (debut + pd.Timedelta(hours=1)) > limites
        if fuite.any():
            jour = jours_cibles[fuite][0]
            raise ValueError(
                f"Fuite : la prévision du {jour:%Y-%m-%d} à {heure} h utilise le "
                f"{jour - pd.Timedelta(days=recul):%Y-%m-%d} à {heure} h, inconnu à 14 h "
                f"le {jour - pd.Timedelta(days=1):%Y-%m-%d}"
            )


# --- Tout calculer pour une période ------------------------------------------
def jours_de_la_periode(nom_periode):
    """Les jours cibles d'une période du découpage (config.DECOUPAGE)."""
    debut, fin = config.DECOUPAGE[nom_periode]
    return pd.date_range(debut, fin, freq="D")


def evaluer_periode(nom_periode, conso_h=None):
    """Calcule B0, B1 et B2 sur une période et renvoie (scores, vraies valeurs, prévisions).

    Les jours de changement d'heure sont retirés de la notation (piste de la décision 11) :
    ils n'ont pas 24 heures, on ne peut donc pas les comparer heure par heure.
    """
    if nom_periode == "test":
        raise ValueError("Le test 2024-2025 ne s'utilise qu'une fois, à la fin, après gel des choix.")

    conso_h = rte.lire_prepare() if conso_h is None else conso_h
    conso_jour = consommation_par_jour(conso_h)
    jours = jours_de_la_periode(nom_periode)
    jours = jours[~jours.isin(jours_changement_heure(conso_h))]

    for decalages in (DECALAGES_B0, DECALAGE_B1, DECALAGES_B2):
        verifier_disponibilite(jours, decalages)

    reel = conso_jour.reindex(jours)
    previsions = {
        "B0 : veille effective": benchmark_b0(conso_jour, jours),
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
