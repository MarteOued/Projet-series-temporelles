"""Reconstruit toute la météo depuis zéro, en une seule commande.

    python -m src.pipeline_meteo                      # pipeline complet
    python -m src.pipeline_meteo --benchmark-spatial  # + comparaison des méthodes spatiales

Les modules restent séparés (chacun garde son rôle, ses journaux et ses contrôles) ;
ce fichier ne fait que les lancer dans le bon ordre :

 1. meteo                            téléchargement : archives SYNOP, stations, postes, régions
 2. benchmark_imputation (option)    comparaison des méthodes spatiales (apprentissage, ~5 min)
 3. imputation_meteo                 imputation spatiale (voisins au même instant, appris sur 2016-2022)
 4. diagnostic_trous_meteo           diagnostic des trous restants (pannes du réseau)
 5. benchmark_imputation_temporelle  choix de la méthode causale par longueur de trou (apprentissage)
 6. imputation_temporelle            imputation temporelle CAUSALE (le passé seulement)
 7. correction_anomalies_meteo       anomalies détectées par la règle, corrigées par les voisins
 8. diagnostic_anomalies_meteo       contrôle des corrections
 9. validation_meteo                 contrôles de la matrice finale
10. temperature_france               trois températures France candidates, grille horaire

Étapes coûteuses : 1 (téléchargement d'environ 80 Mo, une seule fois, mis en cache)
et 5 (environ 10 minutes).
"""
import argparse
import time

from src import (
    benchmark_imputation,
    benchmark_imputation_temporelle,
    correction_anomalies_meteo,
    diagnostic_anomalies_meteo,
    diagnostic_trous_meteo,
    imputation_meteo,
    imputation_temporelle,
    meteo,
    temperature_france,
    validation_meteo,
)

ETAPES = [
    ("Téléchargement", meteo.main),
    ("Imputation spatiale", imputation_meteo.main),
    ("Diagnostic des trous", diagnostic_trous_meteo.main),
    ("Benchmark temporel (choix de la méthode causale)", benchmark_imputation_temporelle.main),
    ("Imputation temporelle causale", imputation_temporelle.main),
    ("Correction des anomalies", correction_anomalies_meteo.main),
    ("Diagnostic des anomalies", diagnostic_anomalies_meteo.main),
    ("Validation de la matrice finale", validation_meteo.main),
    ("Températures France candidates", temperature_france.preparer),
]


def lancer(avec_benchmark_spatial=False):
    etapes = list(ETAPES)
    if avec_benchmark_spatial:
        etapes.insert(1, ("Benchmark spatial", benchmark_imputation.main))

    for numero, (nom, fonction) in enumerate(etapes, start=1):
        debut = time.time()
        print(f"\n{'#' * 90}\n# ÉTAPE {numero}/{len(etapes)} : {nom}\n{'#' * 90}")
        fonction()
        print(f"\n>>> {nom} : terminé en {time.time() - debut:.0f} s")


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--benchmark-spatial", action="store_true",
                         help="lancer aussi la comparaison des méthodes spatiales (environ 5 min)")
    lancer(parseur.parse_args().benchmark_spatial)
