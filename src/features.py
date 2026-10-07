"""Construction causale des variables de prévision.

Une observation de modélisation correspond à une prévision effectuée
à 14 h (heure de Paris) le jour J pour une heure H du jour J+1.

Ce module ne doit jamais utiliser une observation qui n'était pas
disponible à l'origine de la prévision.

Les règles de disponibilité sont centralisées dans ``src.protocole``.
"""

from __future__ import annotations

import pandas as pd

from src import config, protocole


# ===========================================================================
# Constantes
# ===========================================================================

COLONNES_CALENDRIER = [
    "jour_semaine",
    "mois",
    "weekend",
    "ferie",
    "veille_ferie",
    "lendemain_ferie",
    "pont_potentiel",
    "vacances_A",
    "vacances_B",
    "vacances_C",
    "nb_zones_vacances",
    "periode_noel",
]

COLONNES_TEMPERATURE_OPERATIONNELLE = [
    "temp_8_villes",
    "temp_38_simple",
    "temp_38_ponderee",
]

SEUIL_CHAUFFAGE_C = 15.0
SEUIL_CLIMATISATION_C = 22.0
ALPHA_LISSAGE_TEMPERATURE = 0.5


# ===========================================================================
# Utilitaires temporels
# ===========================================================================

def normaliser_jour_local(jour) -> pd.Timestamp:
    """Retourne une date sans fuseau représentant un jour civil à Paris."""
    timestamp = pd.Timestamp(jour)

    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(config.FUSEAU)

    return timestamp.normalize().tz_localize(None)


def origine_prevision_utc(jour_J) -> pd.Timestamp:
    """Instant de prévision : 14 h Paris le jour J, exprimé en UTC."""
    jour = normaliser_jour_local(jour_J)

    return pd.Timestamp(
        f"{jour:%Y-%m-%d} {config.HEURE_ORIGINE:02d}:00",
        tz=config.FUSEAU,
    ).tz_convert("UTC")


def jour_cible(jour_J) -> pd.Timestamp:
    """Jour J+1 correspondant à une prévision lancée le jour J."""
    return normaliser_jour_local(jour_J) + pd.Timedelta(days=1)


def instant_cible_utc(jour_J, heure_cible: int) -> pd.Timestamp:
    """Timestamp UTC de l'heure H du jour J+1."""
    if not 0 <= int(heure_cible) <= 23:
        raise ValueError(
            "heure_cible doit être comprise entre 0 et 23."
        )

    cible = jour_cible(jour_J)

    local = pd.Timestamp(
        f"{cible:%Y-%m-%d} {int(heure_cible):02d}:00",
        tz=config.FUSEAU,
    )

    return local.tz_convert("UTC")


def horizon_heures(jour_J, heure_cible: int) -> int:
    """Horizon entre 14 h J et l'heure cible de J+1."""
    origine = origine_prevision_utc(jour_J)
    cible = instant_cible_utc(jour_J, heure_cible)

    return int(
        (cible - origine)
        / pd.Timedelta(hours=1)
    )


# ===========================================================================
# Validation des séries
# ===========================================================================

def verifier_index_utc(
    donnees: pd.DataFrame | pd.Series,
) -> None:
    """Vérifie les propriétés nécessaires d'un index temporel UTC."""
    if not isinstance(donnees.index, pd.DatetimeIndex):
        raise TypeError(
            "L'index doit être un pandas.DatetimeIndex."
        )

    if donnees.index.tz is None:
        raise ValueError(
            "L'index doit être timezone-aware."
        )

    if str(donnees.index.tz) != "UTC":
        raise ValueError(
            "L'index doit être en UTC."
        )

    if not donnees.index.is_monotonic_increasing:
        raise ValueError(
            "L'index temporel doit être trié."
        )

    if donnees.index.has_duplicates:
        raise ValueError(
            "L'index temporel contient des doublons."
        )


def valeur_exacte(
    serie: pd.Series,
    instant: pd.Timestamp,
):
    """Lit une valeur à un instant exact sans interpolation implicite."""
    if instant not in serie.index:
        raise KeyError(
            "Aucune observation disponible à l'instant requis : "
            f"{instant}"
        )

    return serie.loc[instant]


# ===========================================================================
# Retards de consommation
# ===========================================================================

def instant_retard_cible(
    jour_J,
    heure_cible: int,
    jours_retard: int,
) -> pd.Timestamp:
    """Instant UTC situé exactement N x 24 heures avant la cible.

    Les retards de consommation sont définis en heures écoulées réelles.
    Le calcul en UTC évite toute ambiguïté lors des changements d'heure
    Europe/Paris.
    """
    if jours_retard < 1:
        raise ValueError(
            "jours_retard doit être supérieur ou égal à 1."
        )

    if not 0 <= int(heure_cible) <= 23:
        raise ValueError(
            "heure_cible doit être comprise entre 0 et 23."
        )

    cible_utc = instant_cible_utc(
        jour_J,
        heure_cible,
    )

    return (
        cible_utc
        - pd.Timedelta(
            hours=24 * int(jours_retard)
        )
    )


def consommation_retard(
    consommation: pd.Series,
    jour_J,
    heure_cible: int,
    jours_retard: int,
):
    """Retourne un retard seulement s'il était disponible à 14 h J."""
    verifier_index_utc(consommation)

    instant = instant_retard_cible(
        jour_J,
        heure_cible,
        jours_retard,
    )

    if not protocole.est_connue_a_14h(
        instant,
        jour_J,
    ):
        raise ValueError(
            "Fuite temporelle : le retard demandé n'était pas "
            "disponible à 14 h le "
            f"{normaliser_jour_local(jour_J).date()}."
        )

    return valeur_exacte(
        consommation,
        instant,
    )


def consommation_veille_effective(
    consommation: pd.Series,
    jour_J,
    heure_cible: int,
):
    """Retard le plus récent autorisé pour l'heure cible."""
    jours_retard = (
        1
        if int(heure_cible)
        <= config.DERNIERE_HEURE_CONSO_CONNUE
        else 2
    )

    valeur = consommation_retard(
        consommation,
        jour_J,
        heure_cible,
        jours_retard,
    )

    retard_effectif = (
        24
        if jours_retard == 1
        else 48
    )

    return valeur, retard_effectif


# ===========================================================================
# Cible
# ===========================================================================

def consommation_cible(
    consommation: pd.Series,
    jour_J,
    heure_cible: int,
):
    """Retourne la consommation à prévoir pour H du jour J+1."""
    verifier_index_utc(consommation)

    instant = instant_cible_utc(
        jour_J,
        heure_cible,
    )

    return valeur_exacte(
        consommation,
        instant,
    )


# ===========================================================================
# Variables calendaires
# ===========================================================================

def verifier_calendrier(
    calendrier: pd.DataFrame,
) -> None:
    """Vérifie la structure minimale du calendrier préparé."""
    colonnes_manquantes = [
        colonne
        for colonne in COLONNES_CALENDRIER
        if colonne not in calendrier.columns
    ]

    if colonnes_manquantes:
        raise ValueError(
            "Colonnes calendaires manquantes : "
            + ", ".join(colonnes_manquantes)
        )

    if calendrier.index.has_duplicates:
        raise ValueError(
            "Le calendrier contient plusieurs lignes "
            "pour une même date."
        )


def _index_calendrier_en_dates(
    calendrier: pd.DataFrame,
) -> pd.DataFrame:
    """Normalise l'index du calendrier en jours civils sans fuseau."""
    resultat = calendrier.copy()

    index = pd.to_datetime(resultat.index)

    if index.tz is not None:
        index = (
            index
            .tz_convert(config.FUSEAU)
            .tz_localize(None)
        )

    resultat.index = index.normalize()
    resultat.index.name = "date"

    return resultat


def variables_calendrier_cible(
    calendrier: pd.DataFrame,
    jour_J,
) -> pd.Series:
    """Retourne les variables calendaires du jour cible J+1."""
    verifier_calendrier(calendrier)

    calendrier_normalise = (
        _index_calendrier_en_dates(
            calendrier
        )
    )

    cible = jour_cible(jour_J)

    if cible not in calendrier_normalise.index:
        raise KeyError(
            "Jour cible absent du calendrier : "
            f"{cible.date()}"
        )

    return calendrier_normalise.loc[
        cible,
        COLONNES_CALENDRIER,
    ].copy()


# ===========================================================================
# Validation météo
# ===========================================================================

def verifier_meteo(
    meteo: pd.DataFrame,
) -> None:
    """Vérifie la structure des températures opérationnelles."""
    verifier_index_utc(meteo)

    manquantes = [
        colonne
        for colonne
        in COLONNES_TEMPERATURE_OPERATIONNELLE
        if colonne not in meteo.columns
    ]

    if manquantes:
        raise ValueError(
            "Colonnes météo opérationnelles manquantes : "
            + ", ".join(manquantes)
        )


def verifier_colonne_temperature(
    colonne_temperature: str,
) -> None:
    """Refuse toute température non opérationnelle."""
    if (
        colonne_temperature
        not in COLONNES_TEMPERATURE_OPERATIONNELLE
    ):
        raise ValueError(
            "La température demandée n'est pas une candidate "
            "opérationnelle autorisée."
        )


# ===========================================================================
# Température à l'origine
# ===========================================================================

def temperature_origine(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
) -> float:
    """Dernière température autorisée avant la prévision."""
    verifier_meteo(meteo)
    verifier_colonne_temperature(
        colonne_temperature
    )

    instant = protocole.limite_meteo_connue(
        jour_J
    )

    valeur = valeur_exacte(
        meteo[colonne_temperature],
        instant,
    )

    return float(valeur)


# ===========================================================================
# Températures journalières historiques
# ===========================================================================

def temperature_journaliere_complete(
    meteo: pd.DataFrame,
    jour,
    colonne_temperature: str,
) -> float:
    """Moyenne d'un jour civil de Paris entièrement observé."""
    verifier_meteo(meteo)
    verifier_colonne_temperature(
        colonne_temperature
    )

    jour_local = normaliser_jour_local(jour)

    debut_local = pd.Timestamp(
        jour_local.date(),
        tz=config.FUSEAU,
    )

    fin_local = (
        debut_local
        + pd.DateOffset(days=1)
    )

    debut_utc = debut_local.tz_convert("UTC")
    fin_utc = fin_local.tz_convert("UTC")

    valeurs = meteo.loc[
        (
            meteo.index >= debut_utc
        )
        & (
            meteo.index < fin_utc
        ),
        colonne_temperature,
    ]

    if valeurs.empty:
        raise KeyError(
            "Aucune température pour le jour "
            f"{jour_local.date()}."
        )

    if valeurs.isna().any():
        raise ValueError(
            "Températures manquantes pour le jour "
            f"{jour_local.date()}."
        )

    return float(valeurs.mean())


def temperature_veille(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
) -> float:
    """Température moyenne du jour J-1."""
    veille = (
        normaliser_jour_local(jour_J)
        - pd.Timedelta(days=1)
    )

    return temperature_journaliere_complete(
        meteo,
        veille,
        colonne_temperature,
    )


def temperatures_journalieres_passees(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
) -> pd.Series:
    """Moyennes des journées complètement terminées avant J."""
    verifier_meteo(meteo)
    verifier_colonne_temperature(
        colonne_temperature
    )

    jour = normaliser_jour_local(jour_J)

    jours_locaux = (
        meteo.index
        .tz_convert(config.FUSEAU)
        .normalize()
        .tz_localize(None)
    )

    masque = jours_locaux < jour

    historique = meteo.loc[
        masque,
        [colonne_temperature],
    ].copy()

    if historique.empty:
        raise ValueError(
            "Historique météo insuffisant avant "
            "le jour de prévision."
        )

    historique["jour_local"] = (
        historique.index
        .tz_convert(config.FUSEAU)
        .normalize()
        .tz_localize(None)
    )

    journalieres = (
        historique
        .groupby("jour_local")[
            colonne_temperature
        ]
        .mean()
    )

    if journalieres.isna().any():
        raise ValueError(
            "Une moyenne journalière météo est manquante."
        )

    return journalieres


# ===========================================================================
# Météo disponible jusqu'à la limite autorisée du jour J
# ===========================================================================

def temperature_jour_j_disponible(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
) -> float:
    """Moyenne météo de J avec uniquement l'information disponible."""
    verifier_meteo(meteo)
    verifier_colonne_temperature(
        colonne_temperature
    )

    jour = normaliser_jour_local(jour_J)

    debut_local = pd.Timestamp(
        jour.date(),
        tz=config.FUSEAU,
    )

    debut_utc = debut_local.tz_convert("UTC")

    limite_utc = (
        protocole.limite_meteo_connue(
            jour
        )
    )

    valeurs = meteo.loc[
        (
            meteo.index >= debut_utc
        )
        & (
            meteo.index <= limite_utc
        ),
        colonne_temperature,
    ]

    if valeurs.empty:
        raise KeyError(
            "Aucune température opérationnelle disponible "
            f"le {jour.date()} avant la limite météo."
        )

    if valeurs.isna().any():
        raise ValueError(
            "Températures manquantes dans la partie connue "
            f"du jour {jour.date()}."
        )

    return float(valeurs.mean())


def temperatures_journalieres_connues(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
) -> pd.Series:
    """Historique journalier causal disponible à l'origine."""
    journalieres = (
        temperatures_journalieres_passees(
            meteo,
            jour_J,
            colonne_temperature,
        )
        .copy()
    )

    jour = normaliser_jour_local(jour_J)

    journalieres.loc[jour] = (
        temperature_jour_j_disponible(
            meteo,
            jour,
            colonne_temperature,
        )
    )

    return journalieres.sort_index()


# ===========================================================================
# Inertie thermique
# ===========================================================================

def temperature_lissee(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
) -> float:
    """Température lissée disponible à l'origine de prévision."""
    if not 0 < float(alpha) <= 1:
        raise ValueError(
            "alpha doit appartenir à ]0, 1]."
        )

    journalieres = (
        temperatures_journalieres_connues(
            meteo,
            jour_J,
            colonne_temperature,
        )
    )

    lissee = (
        journalieres
        .ewm(
            alpha=float(alpha),
            adjust=False,
        )
        .mean()
    )

    return float(lissee.iloc[-1])


# ===========================================================================
# Transformations thermiques
# ===========================================================================

def degres_chauffage(
    temperature: float,
    seuil: float = SEUIL_CHAUFFAGE_C,
) -> float:
    """Degrés de chauffage."""
    return max(
        0.0,
        float(seuil) - float(temperature),
    )


def degres_climatisation(
    temperature: float,
    seuil: float = SEUIL_CLIMATISATION_C,
) -> float:
    """Degrés de climatisation."""
    return max(
        0.0,
        float(temperature) - float(seuil),
    )


def variables_meteo_causales(
    meteo: pd.DataFrame,
    jour_J,
    colonne_temperature: str,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
) -> dict:
    """Construit les variables météo disponibles à l'origine."""
    origine = temperature_origine(
        meteo,
        jour_J,
        colonne_temperature,
    )

    veille = temperature_veille(
        meteo,
        jour_J,
        colonne_temperature,
    )

    lissee = temperature_lissee(
        meteo,
        jour_J,
        colonne_temperature,
        alpha=alpha,
    )

    return {
        f"{colonne_temperature}_origine":
            origine,

        f"{colonne_temperature}_veille":
            veille,

        f"{colonne_temperature}_lissee":
            lissee,

        f"{colonne_temperature}_degres_chauffage_origine":
            degres_chauffage(origine),

        f"{colonne_temperature}_degres_chauffage_lisses":
            degres_chauffage(lissee),

        f"{colonne_temperature}_degres_climatisation_origine":
            degres_climatisation(origine),

        f"{colonne_temperature}_degres_climatisation_lisses":
            degres_climatisation(lissee),
    }


# ===========================================================================
# Pré-calcul météo vectorisé
# ===========================================================================

def preparer_meteo_journaliere(
    meteo: pd.DataFrame,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
) -> pd.DataFrame:
    """Pré-calcule les variables météo causales pour les jours exploitables.

    Un jour J n'est conservé que si la série météo contient effectivement
    l'observation correspondant à ``protocole.limite_meteo_connue(J)``.

    Cette règle permet de gérer les jours incomplets aux bords de la série
    sans fabriquer d'observation et sans utiliser d'information future.
    """
    verifier_meteo(meteo)

    alpha = float(alpha)

    if not 0 < alpha <= 1:
        raise ValueError(
            "alpha doit appartenir à ]0, 1]."
        )

    # ------------------------------------------------------------------
    # Jour civil Paris associé à chaque observation
    # ------------------------------------------------------------------

    jours_locaux = (
        meteo.index
        .tz_convert(config.FUSEAU)
        .normalize()
        .tz_localize(None)
    )

    travail = (
        meteo[
            COLONNES_TEMPERATURE_OPERATIONNELLE
        ]
        .copy()
    )

    travail["jour_local"] = jours_locaux

    # ------------------------------------------------------------------
    # Moyennes journalières
    # ------------------------------------------------------------------

    moyennes_completes = (
        travail
        .groupby("jour_local")[
            COLONNES_TEMPERATURE_OPERATIONNELLE
        ]
        .mean()
        .sort_index()
    )

    if moyennes_completes.isna().any().any():
        raise ValueError(
            "Une moyenne météo journalière est manquante."
        )

    jours_presents = moyennes_completes.index

    # ------------------------------------------------------------------
    # Limite météo de chaque jour
    # ------------------------------------------------------------------

    limites_utc = pd.Series(
        [
            protocole.limite_meteo_connue(jour)
            for jour in jours_presents
        ],
        index=jours_presents,
        dtype="object",
    )

    # ------------------------------------------------------------------
    # Ne conserver comme origines que les jours réellement exploitables
    # ------------------------------------------------------------------

    masque_jours_exploitables = (
        limites_utc.map(
            lambda instant: instant in meteo.index
        )
    )

    jours_exploitables = (
        limites_utc.index[
            masque_jours_exploitables
        ]
    )

    if len(jours_exploitables) == 0:
        raise ValueError(
            "Aucun jour météo exploitable dans la série."
        )

    # ------------------------------------------------------------------
    # EWMA des journées antérieures
    # ------------------------------------------------------------------

    ewma_complete = (
        moyennes_completes
        .ewm(
            alpha=alpha,
            adjust=False,
        )
        .mean()
    )

    ewma_avant_j = (
        ewma_complete
        .shift(1)
    )

    # ------------------------------------------------------------------
    # Partie connue de chaque jour
    # ------------------------------------------------------------------

    limites_observations = (
        travail["jour_local"]
        .map(limites_utc)
    )

    instants = pd.Series(
        travail.index,
        index=travail.index,
    )

    limites_observations.index = travail.index

    masque_connu = (
        instants
        <= limites_observations
    )

    travail_connu = (
        travail.loc[
            masque_connu,
            COLONNES_TEMPERATURE_OPERATIONNELLE
            + ["jour_local"],
        ]
    )

    moyennes_partielles = (
        travail_connu
        .groupby("jour_local")[
            COLONNES_TEMPERATURE_OPERATIONNELLE
        ]
        .mean()
        .reindex(jours_exploitables)
    )

    if moyennes_partielles.isna().any().any():
        jours_problematiques = (
            moyennes_partielles.index[
                moyennes_partielles
                .isna()
                .any(axis=1)
            ]
        )

        raise ValueError(
            "Météo partielle indisponible pour certains jours : "
            + ", ".join(
                str(pd.Timestamp(jour).date())
                for jour in jours_problematiques[:10]
            )
        )

    # ------------------------------------------------------------------
    # Température à la limite météo
    # ------------------------------------------------------------------

    temperatures_origine = pd.DataFrame(
        index=jours_exploitables,
        columns=COLONNES_TEMPERATURE_OPERATIONNELLE,
        dtype=float,
    )

    for jour in jours_exploitables:
        limite = limites_utc.loc[jour]

        temperatures_origine.loc[
            jour,
            COLONNES_TEMPERATURE_OPERATIONNELLE,
        ] = (
            meteo.loc[
                limite,
                COLONNES_TEMPERATURE_OPERATIONNELLE,
            ]
            .astype(float)
            .to_numpy()
        )

    # ------------------------------------------------------------------
    # Construction finale
    # ------------------------------------------------------------------

    resultat = pd.DataFrame(
        index=jours_exploitables
    )

    resultat.index.name = "jour_origine"

    for colonne in (
        COLONNES_TEMPERATURE_OPERATIONNELLE
    ):
        origine = (
            temperatures_origine[colonne]
            .astype(float)
        )

        veille = (
            moyennes_completes[colonne]
            .shift(1)
            .reindex(jours_exploitables)
        )

        etat_precedent = (
            ewma_avant_j[colonne]
            .reindex(jours_exploitables)
        )

        partielle = (
            moyennes_partielles[colonne]
        )

        lissee = (
            alpha * partielle
            + (1.0 - alpha) * etat_precedent
        )

        masque_sans_historique = (
            etat_precedent.isna()
        )

        lissee.loc[
            masque_sans_historique
        ] = (
            partielle.loc[
                masque_sans_historique
            ]
        )

        resultat[
            f"{colonne}_origine"
        ] = origine

        resultat[
            f"{colonne}_veille"
        ] = veille

        resultat[
            f"{colonne}_lissee"
        ] = lissee

        resultat[
            f"{colonne}_degres_chauffage_origine"
        ] = origine.map(
            degres_chauffage
        )

        resultat[
            f"{colonne}_degres_chauffage_lisses"
        ] = lissee.map(
            degres_chauffage
        )

        resultat[
            f"{colonne}_degres_climatisation_origine"
        ] = origine.map(
            degres_climatisation
        )

        resultat[
            f"{colonne}_degres_climatisation_lisses"
        ] = lissee.map(
            degres_climatisation
        )

    return resultat


def variables_meteo_precalculees_jour(
    meteo_journaliere: pd.DataFrame,
    jour_J,
) -> dict:
    """Lit les variables météo pré-calculées pour un jour J."""
    jour = normaliser_jour_local(jour_J)

    if jour not in meteo_journaliere.index:
        raise KeyError(
            "Jour absent du pré-calcul météo : "
            f"{jour.date()}"
        )

    ligne = meteo_journaliere.loc[jour]

    if ligne.isna().any():
        colonnes_manquantes = (
            ligne.index[
                ligne.isna()
            ]
            .tolist()
        )

        raise ValueError(
            "Variables météo pré-calculées manquantes "
            f"pour {jour.date()} : "
            + ", ".join(colonnes_manquantes)
        )

    return {
        colonne: float(valeur)
        for colonne, valeur
        in ligne.items()
    }


# ===========================================================================
# Périodes expérimentales
# ===========================================================================

def periode_jour_cible(
    jour_cible_,
) -> str:
    """Retourne la période associée au jour cible."""
    jour = normaliser_jour_local(
        jour_cible_
    )

    for nom_periode in (
        "apprentissage",
        "validation",
        "test",
    ):
        debut, fin = (
            config.DECOUPAGE[
                nom_periode
            ]
        )

        debut = pd.Timestamp(debut)
        fin = pd.Timestamp(fin)

        if debut <= jour <= fin:
            return nom_periode

    return "hors_periode"


def cible_exclue_covid(
    jour_cible_,
) -> bool:
    """Indique si la cible appartient à la période Covid exclue du fit."""
    jour = normaliser_jour_local(
        jour_cible_
    )

    debut, fin = config.EXCLUSION_COVID

    debut = pd.Timestamp(debut)
    fin = pd.Timestamp(fin)

    return bool(
        debut <= jour <= fin
    )


# ===========================================================================
# Construction d'une observation
# ===========================================================================

def construire_ligne(
    consommation: pd.Series,
    meteo: pd.DataFrame,
    calendrier: pd.DataFrame,
    jour_J,
    heure_cible: int,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
    calendrier_cible_precalcule: pd.Series | None = None,
    meteo_precalculee: dict | None = None,
) -> dict:
    """Construit une observation pour prévoir H du jour J+1."""
    jour_origine = normaliser_jour_local(
        jour_J
    )

    cible_jour = jour_cible(
        jour_origine
    )

    origine_utc = origine_prevision_utc(
        jour_origine
    )

    cible_utc = instant_cible_utc(
        jour_origine,
        heure_cible,
    )

    # Calendrier
    if calendrier_cible_precalcule is None:
        calendrier_cible = (
            variables_calendrier_cible(
                calendrier,
                jour_origine,
            )
        )
    else:
        calendrier_cible = (
            calendrier_cible_precalcule
        )

    # Consommation historique
    (
        veille_effective,
        retard_effectif,
    ) = consommation_veille_effective(
        consommation,
        jour_origine,
        heure_cible,
    )

    lag48 = consommation_retard(
        consommation,
        jour_origine,
        heure_cible,
        jours_retard=2,
    )

    lag168 = consommation_retard(
        consommation,
        jour_origine,
        heure_cible,
        jours_retard=7,
    )

    cible = consommation_cible(
        consommation,
        jour_origine,
        heure_cible,
    )

    ligne = {
        "jour_origine":
            jour_origine,

        "date_heure_origine_utc":
            origine_utc,

        "jour_cible":
            cible_jour,

        "heure_cible":
            int(heure_cible),

        "date_heure_cible_utc":
            cible_utc,

        "horizon_h":
            horizon_heures(
                jour_origine,
                heure_cible,
            ),

        "periode":
            periode_jour_cible(
                cible_jour
            ),

        "exclu_covid":
            cible_exclue_covid(
                cible_jour
            ),

        "conso_veille_effective_MW":
            float(veille_effective),

        "retard_effectif_h":
            int(retard_effectif),

        "conso_lag48_MW":
            float(lag48),

        "conso_lag168_MW":
            float(lag168),
    }

    # Calendrier
    for colonne in COLONNES_CALENDRIER:
        ligne[colonne] = (
            calendrier_cible[colonne]
        )

    # Météo
    if meteo_precalculee is None:
        variables_meteo = {}

        for colonne_temperature in (
            COLONNES_TEMPERATURE_OPERATIONNELLE
        ):
            variables = (
                variables_meteo_causales(
                    meteo,
                    jour_origine,
                    colonne_temperature,
                    alpha=alpha,
                )
            )

            variables_meteo.update(
                variables
            )

    else:
        variables_meteo = meteo_precalculee

    ligne.update(
        variables_meteo
    )

    ligne[
        "consommation_cible_MW"
    ] = float(cible)

    return ligne


# ===========================================================================
# Pré-calcul journalier
# ===========================================================================

def variables_journalieres_precalculees(
    meteo: pd.DataFrame,
    calendrier: pd.DataFrame,
    jour_J,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
    meteo_journaliere: pd.DataFrame | None = None,
) -> tuple[pd.Series, dict]:
    """Pré-calcule les variables communes aux 24 horizons d'un jour J."""
    jour_origine = normaliser_jour_local(
        jour_J
    )

    calendrier_cible = (
        variables_calendrier_cible(
            calendrier,
            jour_origine,
        )
    )

    if meteo_journaliere is not None:
        variables_meteo = (
            variables_meteo_precalculees_jour(
                meteo_journaliere,
                jour_origine,
            )
        )

        return (
            calendrier_cible,
            variables_meteo,
        )

    variables_meteo = {}

    for colonne_temperature in (
        COLONNES_TEMPERATURE_OPERATIONNELLE
    ):
        variables = (
            variables_meteo_causales(
                meteo,
                jour_origine,
                colonne_temperature,
                alpha=alpha,
            )
        )

        variables_meteo.update(
            variables
        )

    return (
        calendrier_cible,
        variables_meteo,
    )


# ===========================================================================
# Changements d'heure
# ===========================================================================

def nombre_heures_jour_local(
    jour,
) -> int:
    """Nombre réel d'heures du jour civil en Europe/Paris."""
    jour = normaliser_jour_local(jour)

    debut = pd.Timestamp(
        jour.date(),
        tz=config.FUSEAU,
    )

    fin = (
        debut
        + pd.DateOffset(days=1)
    )

    return int(
        (
            fin.tz_convert("UTC")
            - debut.tz_convert("UTC")
        )
        / pd.Timedelta(hours=1)
    )


def jour_changement_heure(
    jour,
) -> bool:
    """Vrai pour un jour civil de 23 h ou 25 h."""
    return (
        nombre_heures_jour_local(jour)
        != 24
    )


def heure_locale_valide(
    jour,
    heure: int,
) -> bool:
    """Vérifie qu'une heure civile correspond à un instant unique."""
    jour = normaliser_jour_local(jour)

    if not 0 <= int(heure) <= 23:
        raise ValueError(
            "heure doit être comprise entre 0 et 23."
        )

    naive = (
        jour
        + pd.Timedelta(hours=int(heure))
    )

    try:
        naive.tz_localize(
            config.FUSEAU,
            ambiguous="raise",
            nonexistent="raise",
        )

        return True

    except ValueError:
        return False


def ligne_constructible(
    jour_J,
    heure_cible: int,
) -> bool:
    """Vérifie que l'heure cible appartient à une journée exploitable.

    Les journées de changement d'heure sont exclues comme cibles.
    Un changement d'heure situé uniquement dans l'historique ne doit pas
    supprimer une heure d'une journée cible ordinaire, car les retards de
    consommation sont calculés en UTC par ``instant_retard_cible``.
    """
    origine = normaliser_jour_local(
        jour_J
    )

    cible = jour_cible(
        origine
    )

    if jour_changement_heure(cible):
        return False

    return heure_locale_valide(
        cible,
        heure_cible,
    )


# ===========================================================================
# Construction du dataset
# ===========================================================================

def construire_dataset(
    consommation: pd.Series,
    meteo: pd.DataFrame,
    calendrier: pd.DataFrame,
    debut_cible,
    fin_cible,
    alpha: float = ALPHA_LISSAGE_TEMPERATURE,
) -> pd.DataFrame:
    """Construit le dataset opérationnel entre deux jours cibles inclus."""
    verifier_index_utc(
        consommation
    )

    verifier_meteo(
        meteo
    )

    verifier_calendrier(
        calendrier
    )

    debut = normaliser_jour_local(
        debut_cible
    )

    fin = normaliser_jour_local(
        fin_cible
    )

    if fin < debut:
        raise ValueError(
            "La fin de période doit être "
            "postérieure ou égale au début."
        )

    # Pré-calcul météo unique
    meteo_journaliere = (
        preparer_meteo_journaliere(
            meteo,
            alpha=alpha,
        )
    )

    lignes = []

    for cible in pd.date_range(
        debut,
        fin,
        freq="D",
    ):
        # Les journées DST ne constituent pas des cibles
        # d'évaluation/modélisation.
        if jour_changement_heure(
            cible
        ):
            continue

        origine = (
            cible
            - pd.Timedelta(days=1)
        )

        (
            calendrier_cible,
            variables_meteo,
        ) = (
            variables_journalieres_precalculees(
                meteo=meteo,
                calendrier=calendrier,
                jour_J=origine,
                alpha=alpha,
                meteo_journaliere=meteo_journaliere,
            )
        )

        for heure in range(24):
            if not ligne_constructible(
                origine,
                heure,
            ):
                continue

            ligne = construire_ligne(
                consommation=consommation,
                meteo=meteo,
                calendrier=calendrier,
                jour_J=origine,
                heure_cible=heure,
                alpha=alpha,
                calendrier_cible_precalcule=calendrier_cible,
                meteo_precalculee=variables_meteo,
            )

            lignes.append(ligne)

    dataset = pd.DataFrame(
        lignes
    )

    if dataset.empty:
        return dataset

    cle = [
        "jour_cible",
        "heure_cible",
    ]

    if dataset.duplicated(cle).any():
        doublons = dataset.loc[
            dataset.duplicated(
                cle,
                keep=False,
            ),
            cle,
        ]

        raise ValueError(
            "Doublons détectés dans le dataset :\n"
            + doublons.to_string(index=False)
        )

    if dataset[
        "date_heure_cible_utc"
    ].duplicated().any():
        raise ValueError(
            "Plusieurs observations possèdent "
            "le même instant cible UTC."
        )

    colonnes_interdites = [
        colonne
        for colonne in dataset.columns
        if "meteo_parfaite" in colonne
    ]

    if colonnes_interdites:
        raise ValueError(
            "Colonnes météo parfaite interdites "
            "dans le dataset opérationnel : "
            + ", ".join(colonnes_interdites)
        )

    periodes_valides = {
        "apprentissage",
        "validation",
        "test",
        "hors_periode",
    }

    periodes_inconnues = (
        set(dataset["periode"].unique())
        - periodes_valides
    )

    if periodes_inconnues:
        raise ValueError(
            "Périodes inconnues dans le dataset : "
            + ", ".join(
                sorted(periodes_inconnues)
            )
        )

    return (
        dataset
        .sort_values(
            [
                "jour_cible",
                "heure_cible",
            ]
        )
        .reset_index(drop=True)
    )

# ===========================================================================
# Fichiers d'entrée et de sortie
# ===========================================================================

FICHIER_CONSOMMATION = (
    config.DATA_PREPAREES / "rte" / "conso_horaire_utc.csv"
)

FICHIER_TEMPERATURES = (
    config.DATA_PREPAREES
    / "meteo"
    / "temperatures_france_candidates_horaire_utc.csv"
)

FICHIER_CALENDRIER = (
    config.DATA_PREPAREES / "calendrier" / "calendrier.csv"
)

FICHIER_DATASET = (
    config.DATA_PREPAREES / "dataset_modelisation_2016_2025.csv"
)


def charger_entrees() -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """Relit les trois fichiers préparés (consommation, météo, calendrier).

    Seules les températures opérationnelles sont gardées : les colonnes
    « météo parfaite » ne doivent jamais entrer dans le dataset.
    """
    for fichier, commande in (
        (FICHIER_CONSOMMATION, "python -m src.rte"),
        (FICHIER_TEMPERATURES, "python -m src.pipeline_meteo"),
        (FICHIER_CALENDRIER, "python -m src.calendrier"),
    ):
        if not fichier.exists():
            raise FileNotFoundError(
                f"{fichier} introuvable : lancer d'abord `{commande}`."
            )

    consommation = pd.read_csv(
        FICHIER_CONSOMMATION,
        index_col="date_heure_utc",
        parse_dates=["date_heure_utc"],
    )["consommation_MW"]

    meteo = pd.read_csv(
        FICHIER_TEMPERATURES,
        index_col="date_heure_utc",
        parse_dates=["date_heure_utc"],
    )[COLONNES_TEMPERATURE_OPERATIONNELLE]

    calendrier = pd.read_csv(
        FICHIER_CALENDRIER,
        index_col="date",
        parse_dates=["date"],
    )

    return consommation, meteo, calendrier


def preparer(
    chemin=FICHIER_DATASET,
) -> pd.DataFrame:
    """Construit le dataset de modélisation 2016-2025 et le sauvegarde."""
    consommation, meteo, calendrier = charger_entrees()

    dataset = construire_dataset(
        consommation=consommation,
        meteo=meteo,
        calendrier=calendrier,
        debut_cible=config.DECOUPAGE["apprentissage"][0],
        fin_cible=config.DECOUPAGE["test"][1],
    )

    chemin.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(chemin, index=False)

    return dataset


def main() -> None:
    dataset = preparer()

    print(f"Dataset : {FICHIER_DATASET}")
    print(f"Dimensions : {dataset.shape}")
    print(
        "Jours cibles : "
        f"{dataset['jour_cible'].min()} -> {dataset['jour_cible'].max()}"
    )
    print(dataset["periode"].value_counts().to_string())


if __name__ == "__main__":
    main()
