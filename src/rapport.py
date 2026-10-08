"""Tableaux et figures du rapport, écrits dans report/tables et report/figures.

Utilisation
-----------
    python -m src.rapport

Ce script ne calcule aucun modèle : il lit les fichiers de data/resultats/
(produits par src/experiences.py, src/analyses.py, src/comparaison.py,
src/test_bonus.py et src/visualisation.py) et les met en forme. Les scores sont
recalculés avec src/evaluation.py : ce sont exactement les chiffres du notebook 04
et du tableau de bord.

Chaque tableau est écrit deux fois : en CSV (les chiffres complets) et en Markdown
(arrondi, prêt à coller dans le rapport).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src import visualisation as vis  # noqa: E402

RESULTATS = config.RACINE / "data" / "resultats"
TABLES = config.REPORT_TABLES
FIGURES = config.REPORT_FIGURES

# Mêmes couleurs que le tableau de bord (app/composants.py), validées pour les daltoniens
COULEURS = {"reel_MW": "#0b0b0b", "M2": "#2a78d6", "M3": "#eb6834", "Plafond": "#1baf7a", "M1": "#eda100",
            "M4": "#e87ba4", "B0": "#6f6e69", "B1": "#9a9890", "B2": "#bab9b0"}
TRAITS = {"B0": ":", "B1": "--", "B2": "-.", "Plafond": "--"}
NOMS = {"B0": "B0 · veille effective", "B1": "B1 · semaine précédente", "B2": "B2 · moyenne de 4 semaines",
        "M1": "M1 · calendrier + passé", "M2": "M2 · M1 + température", "M3": "M3 · gradient boosting",
        "M4": "M4 · M1 + ARMA", "Plafond": "Plafond · météo parfaite"}
RAMPE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 200, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.grid": True, "grid.color": "#e1e0d9", "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False, "lines.linewidth": 1.8,
})


# ===========================================================================
# Outils
# ===========================================================================

def lire(nom):
    return pd.read_csv(RESULTATS / f"{nom}.csv")


def previsions(periode):
    p = lire("visualisation_previsions")
    return p[p["periode"] == periode]


def nombre(valeur, decimales=0):
    if pd.isna(valeur):
        return ""
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


def en_markdown(tableau, formats=None):
    """Un tableau Markdown simple (sans dépendance), nombres à la française."""
    formats = formats or {}
    lignes = ["| " + " | ".join(str(c) for c in tableau.columns) + " |",
              "|" + "|".join("---:" if pd.api.types.is_numeric_dtype(tableau[c]) else "---" for c in tableau.columns) + "|"]
    for _, ligne in tableau.iterrows():
        cellules = []
        for c in tableau.columns:
            v = ligne[c]
            cellules.append(nombre(v, formats.get(c, 0)) if isinstance(v, (int, float, np.number)) and not isinstance(v, bool) else str(v))
        lignes.append("| " + " | ".join(cellules) + " |")
    return "\n".join(lignes) + "\n"


def sauver_tableau(tableau, nom, formats=None):
    TABLES.mkdir(parents=True, exist_ok=True)
    tableau.to_csv(TABLES / f"{nom}.csv", index=False)
    (TABLES / f"{nom}.md").write_text(en_markdown(tableau, formats), encoding="utf-8")
    print(f"  -> report/tables/{nom}.csv et .md")


def sauver_figure(fig, nom):
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{nom}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  -> report/figures/{nom}.png")


# ===========================================================================
# Tableaux
# ===========================================================================

def tableau_comparaison_test():
    s = vis.scores(previsions("test"))
    t = pd.DataFrame({
        "Méthode": [NOMS[m] for m in s.index],
        "MAE (MW)": s["MAE (MW)"], "RMSE (MW)": s["RMSE (MW)"], "MAPE (%)": s["MAPE (%)"],
        "Biais (MW)": s["biais (MW)"], "Énergie du jour (GWh)": s["erreur énergie du jour (GWh, absolue)"],
        "Pointe (MW)": s["erreur pointe (MW, absolue)"],
        "Heure de pointe exacte (%)": s["heure de pointe exacte (% des jours)"],
    }).reset_index(drop=True)
    sauver_tableau(t, "tab1_comparaison_test_2024_2025",
                   {"MAPE (%)": 1, "Énergie du jour (GWh)": 1, "Heure de pointe exacte (%)": 0})


def tableau_trois_periodes():
    lignes = []
    for m in vis.METHODES:
        ligne = {"Méthode": NOMS[m]}
        for periode, titre in vis.PERIODES.items():
            s = vis.scores(previsions(periode))
            ligne[f"MAE {titre} (MW)"] = s.loc[m, "MAE (MW)"]
        lignes.append(ligne)
    t = pd.DataFrame(lignes)
    jours = {titre: int(vis.scores(previsions(p))["nb_jours"].iloc[0]) for p, titre in vis.PERIODES.items()}
    t.columns = ["Méthode"] + [f"{c} · {jours[c[4:-5]]} j" for c in t.columns[1:]]
    sauver_tableau(t, "tab2_mae_trois_periodes")


def tableau_significativite():
    fichiers = {"Validation 2023": "significativite_2023", "Test 2024-2025": "significativite_2024_2025",
                "Test bonus 2026": "test_bonus_2026_significativite"}
    lignes = []
    for titre, nom in fichiers.items():
        t = lire(nom)
        for r in t.itertuples():
            lignes.append({"Période": titre, "M2 contre": vis.NOMS_COURTS[r.autre_methode], "Perte": r.perte,
                           "Jours où M2 fait mieux (%)": 100 * r.part_jours_reference_meilleure,
                           "p-valeur": r.p_valeur, "Conclusion": r.conclusion})
    sauver_tableau(pd.DataFrame(lignes), "tab3_significativite_diebold_mariano",
                   {"p-valeur": 3, "Jours où M2 fait mieux (%)": 0})


def tableau_ablations():
    lignes = []
    noms_lags = {"LAG-A": "veille (matin) + semaine passée", "LAG-B": "veille (matin) + avant-veille + semaine passée",
                 "LAG-C": "avant-veille + semaine passée", "LAG-D": "semaine passée seulement"}
    for r in lire("ablation_lags_m1_2023").itertuples():
        lignes.append(("Retards (M1)", noms_lags[r.variante], r.MAE_MW, r.variante == "LAG-B"))
    for r in lire("ablation_calendrier_m1_2023").itertuples():
        lignes.append(("Calendrier (M1)", r.variables.replace("_", " ").replace(" + ", ", "), r.MAE_MW, r.variante == "CAL-D"))
    noms_meteo = {"M2-A": "température de 13 h seule", "M2-B": "+ température de la veille", "M2-C": "+ température lissée",
                  "M2-D": "13 h, lissée, degrés de chauffage", "M2-E": "+ degrés de climatisation", "M2-F": "les 7 variables"}
    meteo = lire("ablation_m2_2023")
    for r in meteo[meteo["candidat_temperature"] == "temp_38_ponderee"].itertuples():
        lignes.append(("Variables de température (M2)", noms_meteo[r.variante_meteo], r.MAE_MW, r.variante_meteo == "M2-F"))
    for r in meteo[meteo["variante_meteo"] == "M2-F"].itertuples():
        lignes.append(("Température France (M2)", r.candidat_temperature, r.MAE_MW, r.candidat_temperature == "temp_38_ponderee"))
    for r in lire("decision14_un_modele_contre_24_2023").itertuples():
        lignes.append(("Forme du modèle (M1)", r.forme, r.MAE_MW, r.forme.startswith("24")))
    for r in lire("selection_m3_validation_2023").itertuples():
        lignes.append(("Réglage de M3", f"{r.configuration} : {r.max_leaf_nodes} feuilles, {r.max_iter} étapes, pas {r.learning_rate}",
                       r.MAE_MW, r.configuration == "M3-1"))
    for r in lire("selection_m4_validation_2023").itertuples():
        lignes.append(("Réglage de M4", f"ARMA({r.p},{r.q})", r.MAE_MW, r.configuration == "M4-1"))
    for r in lire("sensibilite_covid_2023").itertuples():
        lignes.append(("Confinement 2020", f"{r.modele} {'sans' if r.confinement_retire else 'avec'} le confinement",
                       r.MAE_MW, bool(r.confinement_retire)))
    t = pd.DataFrame(lignes, columns=["Choix testé", "Variante", "MAE 2023 (MW)", "Retenu"])
    t["Retenu"] = t["Retenu"].map({True: "oui", False: ""})
    sauver_tableau(t, "tab4_choix_sur_2023", {"MAE 2023 (MW)": 0})


def tableau_erreurs_par_groupe():
    g = lire("erreurs_par_groupe_2024_2025")
    g["methode"] = g["methode"].map(vis.NOMS_COURTS)
    ordres = {"saison": ["hiver", "printemps", "été", "automne"],
              "type_jour": ["ouvré", "week-end", "pont", "férié", "Noël"],
              "ferie_selon_jour": ["férié en semaine", "férié le week-end"],
              "classe_temperature": ["< 5 °C", "5-10 °C", "10-15 °C", "15-20 °C", "> 20 °C"]}
    titres = {"saison": "Saison", "type_jour": "Type de jour", "ferie_selon_jour": "Férié", "classe_temperature": "Température"}
    lignes = []
    for critere, ordre in ordres.items():
        sous = g[g["critere"] == critere]
        pivot = sous.pivot(index="groupe", columns="methode", values="MAE_MW")
        nb = sous.groupby("groupe")["nb_jours"].first()
        for groupe in ordre:
            if groupe in pivot.index:
                lignes.append({"Critère": titres[critere], "Groupe": groupe, "Jours": int(nb[groupe]),
                               **{m: pivot.loc[groupe, m] for m in ["B0", "M1", "M2", "M3", "Plafond"]}})
    sauver_tableau(pd.DataFrame(lignes), "tab5_erreurs_par_groupe_test")


def categorie_enonce(ligne):
    """Classement des pires jours dans la grille de l'énoncé."""
    if ligne["MAE_Plafond_MW"] < 0.5 * ligne["MAE_MW"]:
        return "Limite des données : pas de prévision météo à 14 h (redoux non anticipé)"
    if ligne["type_jour"] in ("férié", "pont", "Noël"):
        return "Limite du modèle : jour spécial du calendrier, peu d'exemples"
    return "Non classé : ni la météo ni le calendrier ne l'expliquent"


def tableau_pires_jours():
    morceaux = []
    for nom, titre in [("pires_jours_m2_2024_2025", "Test 2024-2025"), ("test_bonus_2026_pires_jours_m2", "Test bonus 2026")]:
        t = lire(nom)
        morceaux.append(pd.DataFrame({
            "Période": titre, "Jour": pd.to_datetime(t["jour_cible"]).dt.strftime("%d/%m/%Y"),
            "Type": t["type_jour"], "T veille (°C)": t["temperature_veille_C"], "T jour (°C)": t["temperature_jour_cible_C"],
            "MAE M2 (MW)": t["MAE_MW"], "MAE plafond (MW)": t["MAE_Plafond_MW"],
            "Sens": np.where(t["biais_MW"] > 0, "trop haut", "trop bas"),
            "Catégorie (grille de l'énoncé)": [categorie_enonce(l) for _, l in t.iterrows()],
        }))
    sauver_tableau(pd.concat(morceaux, ignore_index=True), "tab6_pires_jours",
                   {"T veille (°C)": 1, "T jour (°C)": 1})


# ===========================================================================
# Figures
# ===========================================================================

def figure_donnees():
    j = lire("visualisation_jours")
    j["jour"] = pd.to_datetime(j["jour"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
    a.plot(j["jour"], j["conso_moyenne_MW"] / 1000, color=COULEURS["M2"], linewidth=0.7)
    for debut, fin, nom, opacite in [("2023-01-01", "2023-12-31", "valid.", 0.05), ("2024-01-01", "2025-12-31", "test", 0.09),
                                     ("2026-01-01", "2026-06-30", "bonus", 0.14)]:
        d0, d1 = pd.Timestamp(debut), pd.Timestamp(fin)
        a.axvspan(d0, d1, color="#0b0b0b", alpha=opacite, linewidth=0)
        a.text(d0 + (d1 - d0) / 2, 1.01, nom, transform=a.get_xaxis_transform(), ha="center", va="bottom",
               fontsize=8, color="#52514e")
    a.set_title("Consommation moyenne de chaque jour (GW)", pad=16)
    j2 = j.dropna(subset=["temperature_C"])
    ouvre = j2["type_jour"] == "ouvré"
    b.scatter(j2.loc[ouvre, "temperature_C"], j2.loc[ouvre, "conso_moyenne_MW"] / 1000, s=3, alpha=0.3,
              color=COULEURS["M2"], label="jours ouvrés")
    b.scatter(j2.loc[~ouvre, "temperature_C"], j2.loc[~ouvre, "conso_moyenne_MW"] / 1000, s=3, alpha=0.3,
              color=COULEURS["M3"], label="week-ends et fériés")
    b.axvline(15, color="#898781", linestyle=":", linewidth=1)
    b.set_title("Le froid fait consommer (GW selon °C)", pad=16)
    b.set_xlabel("température moyenne de la France (°C)")
    b.legend(loc="upper right", markerscale=3, fontsize=8)
    sauver_figure(fig, "fig1_donnees")


def figure_classement():
    ordre = vis.scores(previsions("test"))["MAE (MW)"].sort_values().index.tolist()
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    y = np.arange(len(ordre))
    hauteur = 0.26
    for k, (periode, titre) in enumerate(vis.PERIODES.items()):
        s = vis.scores(previsions(periode))["MAE (MW)"]
        ax.barh(y + (k - 1) * hauteur, [s[m] for m in ordre], height=hauteur, color=RAMPE[2 + 2 * k],
                label=titre, edgecolor="white", linewidth=0.8)
    s = vis.scores(previsions("test"))["MAE (MW)"]
    plus_long = {m: max(vis.scores(previsions(p))["MAE (MW)"][m] for p in vis.PERIODES) for m in ordre}
    for i, m in enumerate(ordre):
        ax.text(plus_long[m] + 50, y[i], nombre(s[m]) + " MW", va="center", fontsize=8, color="#0b0b0b")
    ax.set_xlim(0, max(plus_long.values()) * 1.16)
    ax.set_yticks(y, [NOMS[m] for m in ordre])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("erreur moyenne par heure prévue (MW) · chiffres : test 2024-2025")
    ax.set_title("Toutes les méthodes, sur les mêmes jours de chaque période")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=8)
    sauver_figure(fig, "fig2_classement_trois_periodes")


def figure_heures():
    p = previsions("test")
    fig, ax = plt.subplots(figsize=(8.5, 3.4))
    for m in ["B0", "M1", "M2", "Plafond"]:
        ax.plot(range(24), (p[m] - p["reel_MW"]).abs().groupby(p["heure"]).mean(), color=COULEURS[m],
                linestyle=TRAITS.get(m, "-"), marker="o", markersize=3, label=NOMS[m])
    ax.axvline(12.5, color="#898781", linestyle=":", linewidth=1)
    ax.text(12.7, 0.6, "à partir de 13 h : la veille n'est\npas encore publiée à 14 h", transform=ax.get_xaxis_transform(),
            va="center", fontsize=8, color="#52514e")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("heure de la journée (Paris)")
    ax.set_ylabel("MW")
    ax.set_title("Erreur moyenne par heure, test 2024-2025")
    ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    sauver_figure(fig, "fig3_erreur_par_heure")


def figure_biais():
    p = lire("visualisation_previsions")
    p["mois"] = p["jour_cible"].str[:7]
    biais = pd.DataFrame({m: (p[m] - p["reel_MW"]).groupby(p["mois"]).mean() for m in ["B0", "M2", "Plafond"]})
    fig, ax = plt.subplots(figsize=(9, 3.4))
    x = np.arange(len(biais))
    ax.bar(x, biais["M2"], color=COULEURS["M2"], width=0.75, label=NOMS["M2"])
    for m in ["Plafond", "B0"]:
        ax.plot(x, biais[m], color=COULEURS[m], linestyle=TRAITS.get(m, "-"), marker="o", markersize=3, label=NOMS[m])
    ax.axhline(0, color="#0b0b0b", linewidth=0.8)
    ax.set_xticks(x[::3], [f"{MOIS[int(m[5:]) - 1]}\n{m[:4]}" for m in biais.index[::3]], rotation=0, fontsize=8)
    ax.set_ylabel("MW (au-dessus de 0 : trop haut)")
    ax.set_title("Biais moyen par mois : les modèles prévoyaient trop depuis 2023")
    ax.legend(fontsize=8, ncol=3, loc="upper right")
    sauver_figure(fig, "fig4_biais_par_mois")


def figure_carte_heure_mois():
    p = previsions("test").copy()
    p["mois"] = pd.to_datetime(p["jour_cible"]).dt.month
    carte = (p["M2"] - p["reel_MW"]).abs().groupby([p["heure"], p["mois"]]).mean().unstack()
    fig, ax = plt.subplots(figsize=(7, 5))
    from matplotlib.colors import LinearSegmentedColormap
    image = ax.imshow(carte.values, aspect="auto", cmap=LinearSegmentedColormap.from_list("bleu", RAMPE))
    ax.set_xticks(range(12), MOIS, fontsize=8)
    ax.set_yticks(range(0, 24, 2), [f"{h} h" for h in range(0, 24, 2)], fontsize=8)
    ax.grid(False)
    ax.set_title("Erreur moyenne de M2 par heure et par mois (MW), test 2024-2025")
    fig.colorbar(image, ax=ax, shrink=0.8, label="MW")
    sauver_figure(fig, "fig5_carte_heure_mois")


def figure_pires_jours():
    t = lire("pires_jours_m2_2024_2025")
    p = previsions("test")
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=False)
    for ax, ligne in zip(axes, t.itertuples()):
        d = p[p["jour_cible"] == ligne.jour_cible].sort_values("heure")
        for m, epaisseur in (("reel_MW", 2.6), ("M2", 1.8), ("Plafond", 1.8)):
            ax.plot(d["heure"], d[m] / 1000, color=COULEURS[m], linewidth=epaisseur, linestyle=TRAITS.get(m, "-"),
                    label={"reel_MW": "réalité", "M2": "M2", "Plafond": "plafond (vraie météo)"}[m])
        jour = pd.Timestamp(ligne.jour_cible)
        ax.set_title(f"{jour:%d/%m/%Y} · {ligne.type_jour}\n", fontsize=10)
        ax.text(0, 1.02, f"erreur M2 {nombre(ligne.MAE_MW)} MW · plafond {nombre(ligne.MAE_Plafond_MW)} MW · "
                f"{nombre(ligne.temperature_veille_C, 1)} → {nombre(ligne.temperature_jour_cible_C, 1)} °C",
                transform=ax.transAxes, fontsize=7.5, color="#52514e")
        ax.set_xticks(range(0, 24, 6))
        ax.set_xlabel("heure")
    axes[0].set_ylabel("GW")
    gestion, etiquettes = axes[0].get_legend_handles_labels()
    fig.legend(gestion, etiquettes, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, fontsize=8)
    fig.suptitle("Les 3 pires journées de M2 (test 2024-2025)", x=0.01, y=1.06, ha="left", fontweight="bold", fontsize=11)
    sauver_figure(fig, "fig6_pires_jours")


def figure_ablations():
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.4))
    lags = lire("ablation_lags_m1_2023")
    noms = {"LAG-A": "veille + semaine passée", "LAG-B": "veille + avant-veille\n+ semaine passée",
            "LAG-C": "avant-veille + semaine passée", "LAG-D": "semaine passée seule"}
    a.barh([noms[v] for v in lags["variante"]], lags["MAE_MW"],
           color=[COULEURS["M2"] if v == "LAG-B" else COULEURS["B2"] for v in lags["variante"]])
    a.invert_yaxis()
    a.set_title("Consommations passées (M1)")
    meteo = lire("ablation_m2_2023")
    meteo = meteo[meteo["candidat_temperature"] == "temp_38_ponderee"]
    noms_m = {"M2-A": "13 h seule", "M2-B": "+ veille", "M2-C": "+ lissée", "M2-D": "13 h, lissée, chauffage",
              "M2-E": "+ climatisation", "M2-F": "les 7 variables"}
    b.scatter(meteo["MAE_MW"], [noms_m[v] for v in meteo["variante_meteo"]], s=60, zorder=3,
              color=[COULEURS["M2"] if v == "M2-F" else COULEURS["B0"] for v in meteo["variante_meteo"]])
    for valeur, nom in zip(meteo["MAE_MW"], meteo["variante_meteo"]):
        b.text(valeur + 6, noms_m[nom], nombre(valeur), va="center", fontsize=8, color="#52514e")
    b.axvline(lire("ablation_lags_m1_2023").set_index("variante").loc["LAG-B", "MAE_MW"], color=COULEURS["M1"],
              linestyle="--", linewidth=1.2)
    b.text(0.99, 0.98, "tiret : M1, sans météo", transform=b.transAxes, ha="right", va="top", fontsize=8, color="#52514e")
    b.invert_yaxis()
    b.set_xlim(1470, 1690)
    b.set_title("Variables de température (M2)")
    a.set_xlabel("MAE sur 2023 (MW) · en bleu : retenu")
    b.set_xlabel("MAE sur 2023 (MW) · points : axe zoomé · en bleu : retenu")
    a.grid(axis="y", visible=False)
    sauver_figure(fig, "fig7_ablations_2023")


def main():
    print("Tableaux")
    tableau_comparaison_test()
    tableau_trois_periodes()
    tableau_significativite()
    tableau_ablations()
    tableau_erreurs_par_groupe()
    tableau_pires_jours()
    print("Figures")
    figure_donnees()
    figure_classement()
    figure_heures()
    figure_biais()
    figure_carte_heure_mois()
    figure_pires_jours()
    figure_ablations()


if __name__ == "__main__":
    main()
