| Méthode | MAE (MW) | RMSE (MW) | MAPE (%) | Biais (MW) | Énergie du jour (GWh) | Pointe (MW) | Heure de pointe exacte (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 · veille effective | 3 205 | 4 377 | 6,4 | -67 | 72,6 | 3 332 | 50 |
| B1 · semaine précédente | 3 337 | 4 997 | 6,2 | -153 | 76,7 | 3 458 | 67 |
| B2 · moyenne de 4 semaines | 3 649 | 5 224 | 6,9 | -141 | 85,0 | 3 735 | 70 |
| M1 · calendrier + passé | 1 584 | 2 296 | 3,0 | 342 | 33,9 | 1 731 | 61 |
| M2 · M1 + température | 1 331 | 1 856 | 2,6 | 518 | 28,4 | 1 455 | 68 |
| M3 · gradient boosting | 1 349 | 1 951 | 2,6 | 583 | 27,5 | 1 517 | 60 |
| M4 · M1 + ARMA | 1 591 | 2 321 | 3,0 | 271 | 33,6 | 1 744 | 57 |
| Plafond · météo parfaite | 1 044 | 1 419 | 2,1 | 463 | 21,3 | 1 128 | 72 |
