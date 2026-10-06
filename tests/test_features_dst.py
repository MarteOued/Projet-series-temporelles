import pandas as pd
import pytest

from src import features


# ===========================================================================
# Retards définis en temps UTC réel
# ===========================================================================

@pytest.mark.parametrize(
    "jours_retard",
    [1, 2, 7],
)
@pytest.mark.parametrize(
    ("jour_origine", "heure_cible"),
    [
        # Juste après le changement d'heure de printemps 2023.
        ("2023-03-26", 2),

        # Juste après le changement d'heure d'automne 2023.
        ("2023-10-29", 2),
    ],
)
def test_instant_retard_est_exact_en_utc(
    jour_origine,
    heure_cible,
    jours_retard,
):
    cible_utc = features.instant_cible_utc(
        pd.Timestamp(jour_origine),
        heure_cible,
    )

    retard_utc = features.instant_retard_cible(
        pd.Timestamp(jour_origine),
        heure_cible,
        jours_retard,
    )

    assert (
        cible_utc - retard_utc
        == pd.Timedelta(
            hours=24 * jours_retard
        )
    )


# ===========================================================================
# Non-régression : jours ordinaires situés après un changement d'heure
# ===========================================================================

@pytest.mark.parametrize(
    "jour_origine",
    [
        # DST printemps 2023 : 26 mars.
        # Les anciennes règles supprimaient H=2 pour les cibles
        # J+1, J+2 et J+7.
        "2023-03-26",  # cible 27 mars
        "2023-03-27",  # cible 28 mars
        "2023-04-01",  # cible 2 avril

        # DST automne 2023 : 29 octobre.
        "2023-10-29",  # cible 30 octobre
        "2023-10-30",  # cible 31 octobre
        "2023-11-04",  # cible 5 novembre
    ],
)
def test_heure_2_reste_constructible_apres_dst(
    jour_origine,
):
    assert features.ligne_constructible(
        pd.Timestamp(jour_origine),
        2,
    )


# ===========================================================================
# Les vraies journées DST restent exclues comme cibles
# ===========================================================================

@pytest.mark.parametrize(
    "jour_origine",
    [
        # cible = 26 mars 2023 : passage à l'heure d'été
        "2023-03-25",

        # cible = 29 octobre 2023 : passage à l'heure d'hiver
        "2023-10-28",
    ],
)
def test_jour_dst_cible_est_exclu(
    jour_origine,
):
    for heure in range(24):
        assert not features.ligne_constructible(
            pd.Timestamp(jour_origine),
            heure,
        )


# ===========================================================================
# Détection des journées de changement d'heure
# ===========================================================================

@pytest.mark.parametrize(
    ("jour", "nombre_heures"),
    [
        ("2023-03-25", 24),
        ("2023-03-26", 23),
        ("2023-03-27", 24),

        ("2023-10-28", 24),
        ("2023-10-29", 25),
        ("2023-10-30", 24),
    ],
)
def test_nombre_heures_jour_local(
    jour,
    nombre_heures,
):
    assert (
        features.nombre_heures_jour_local(
            pd.Timestamp(jour)
        )
        == nombre_heures
    )


@pytest.mark.parametrize(
    "jour",
    [
        "2023-03-26",
        "2023-10-29",
    ],
)
def test_detection_jour_changement_heure(
    jour,
):
    assert features.jour_changement_heure(
        pd.Timestamp(jour)
    )


@pytest.mark.parametrize(
    "jour",
    [
        "2023-03-25",
        "2023-03-27",
        "2023-10-28",
        "2023-10-30",
    ],
)
def test_jour_ordinaire_pas_dst(
    jour,
):
    assert not features.jour_changement_heure(
        pd.Timestamp(jour)
    )


# ===========================================================================
# Validité des heures civiles locales
# ===========================================================================

def test_heure_2_inexistante_au_printemps():
    assert not features.heure_locale_valide(
        pd.Timestamp("2023-03-26"),
        2,
    )


def test_heure_2_ambigue_en_automne():
    assert not features.heure_locale_valide(
        pd.Timestamp("2023-10-29"),
        2,
    )


@pytest.mark.parametrize(
    "heure",
    range(24),
)
def test_toutes_heures_valides_jour_ordinaire(
    heure,
):
    assert features.heure_locale_valide(
        pd.Timestamp("2023-03-27"),
        heure,
    )


# ===========================================================================
# Vérification explicite des lags autour du DST
# ===========================================================================

def test_lag24_printemps_ne_pointe_pas_sur_heure_inexistante():
    jour_origine = pd.Timestamp(
        "2023-03-26"
    )

    cible = features.instant_cible_utc(
        jour_origine,
        2,
    )

    lag24 = features.instant_retard_cible(
        jour_origine,
        2,
        1,
    )

    assert cible == pd.Timestamp(
        "2023-03-27 00:00:00",
        tz="UTC",
    )

    assert lag24 == pd.Timestamp(
        "2023-03-26 00:00:00",
        tz="UTC",
    )

    assert cible - lag24 == pd.Timedelta(
        hours=24
    )


def test_lag24_automne_est_non_ambigu_en_utc():
    jour_origine = pd.Timestamp(
        "2023-10-29"
    )

    cible = features.instant_cible_utc(
        jour_origine,
        2,
    )

    lag24 = features.instant_retard_cible(
        jour_origine,
        2,
        1,
    )

    assert cible == pd.Timestamp(
        "2023-10-30 01:00:00",
        tz="UTC",
    )

    assert lag24 == pd.Timestamp(
        "2023-10-29 01:00:00",
        tz="UTC",
    )

    assert cible - lag24 == pd.Timedelta(
        hours=24
    )


# ===========================================================================
# Validation des entrées
# ===========================================================================

@pytest.mark.parametrize(
    "heure",
    [-1, 24],
)
def test_instant_retard_refuse_heure_invalide(
    heure,
):
    with pytest.raises(ValueError):
        features.instant_retard_cible(
            pd.Timestamp("2023-06-01"),
            heure,
            1,
        )


@pytest.mark.parametrize(
    "jours_retard",
    [0, -1],
)
def test_instant_retard_refuse_retard_invalide(
    jours_retard,
):
    with pytest.raises(ValueError):
        features.instant_retard_cible(
            pd.Timestamp("2023-06-01"),
            12,
            jours_retard,
        )