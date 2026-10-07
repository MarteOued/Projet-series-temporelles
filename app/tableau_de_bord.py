"""Tableau de bord : la visite guidée du projet, compréhensible par tout le monde.

Lancer depuis la racine du projet :
    streamlit run app/tableau_de_bord.py

Il ne calcule aucun modèle : il lit les fichiers de data/resultats/ (versionnés),
préparés par `python -m src.visualisation`. Les scores sont calculés avec
src/evaluation.py : ce sont les mêmes chiffres que dans le rapport et le notebook 04.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src import visualisation as vis  # noqa: E402

RESULTATS = RACINE / "data" / "resultats"

# ---------------------------------------------------------------------------
# Couleurs et noms
# ---------------------------------------------------------------------------
COULEURS = {
    "reel_MW": "#1f2933", "B0": "#a3a29b", "B1": "#c2c1ba", "B2": "#d6d5cf",
    "M1": "#2a78d6", "M2": "#eb6834", "M3": "#7b4fd6", "M4": "#1b9aaa", "Plafond": "#1baf7a",
}
DESCRIPTIONS = {
    "B0": "Recopie la consommation la plus récente connue : la veille (ou l'avant-veille l'après-midi)",
    "B1": "Recopie le même jour de la semaine précédente",
    "B2": "Moyenne des 4 mêmes jours des semaines précédentes",
    "M1": "Calcul qui apprend du calendrier et des consommations passées",
    "M2": "M1 + la température connue à 14 h  ➜ notre modèle retenu",
    "M3": "Modèle d'apprentissage automatique (arbres de décision) avec les mêmes informations que M2",
    "M4": "M1 + correction de ses erreurs des jours précédents",
    "Plafond": "M2 + la VRAIE température du lendemain (impossible en vrai : sert de repère)",
}
JOURS_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
REACTEUR_MW = (900, 1450)   # puissance d'un réacteur nucléaire français, de 900 à 1 450 MW


def en_une_phrase(texte):
    st.info(f"**En une phrase :** {texte}", icon="💡")


def mw(valeur):
    return f"{valeur:,.0f} MW".replace(",", " ")


# ---------------------------------------------------------------------------
# Données (lues une fois, gardées en mémoire)
# ---------------------------------------------------------------------------
@st.cache_data
def lire(nom):
    return pd.read_csv(RESULTATS / f"{nom}.csv")


@st.cache_data
def previsions():
    return lire("visualisation_previsions")


@st.cache_data
def jours():
    j = lire("visualisation_jours")
    j["jour"] = pd.to_datetime(j["jour"])
    return j.set_index("jour")


@st.cache_data
def scores_periode(periode):
    p = previsions()
    return vis.scores(p[p["periode"] == periode])


@st.cache_data
def erreurs_jour_periode(periode):
    """Erreurs quotidiennes de chaque méthode, avec la description du jour."""
    p = previsions()
    p = p[p["periode"] == periode]
    morceaux = []
    for m in vis.METHODES:
        e = vis.erreurs_quotidiennes(p, m)
        e["methode"] = m
        morceaux.append(e)
    e = pd.concat(morceaux).rename_axis("jour").reset_index()
    return e.join(jours(), on="jour")


def choix_periode(cle, defaut="test"):
    return st.segmented_control(
        "Période", list(vis.PERIODES), default=defaut, format_func=vis.PERIODES.get,
        key=cle, required=True,
    )


def mise_en_page(fig, titre="", hauteur=380, unite="MW"):
    fig.update_layout(
        title=titre, height=hauteur, margin=dict(l=10, r=10, t=50 if titre else 10, b=10),
        legend=dict(orientation="h", y=-0.2), hovermode="x unified",
        separators=", ", yaxis_title=unite,
    )
    return fig


# ===========================================================================
# Pages
# ===========================================================================

def page_accueil():
    st.title("Prévoir la consommation d'électricité de la France, la veille pour le lendemain")
    en_une_phrase(
        "chaque jour à 14 h, on prévoit la consommation d'électricité de la France heure par heure "
        "pour le lendemain, en n'utilisant que ce qu'on sait déjà à 14 h."
    )
    st.markdown(
        "Le gestionnaire du réseau électrique (RTE) doit savoir **la veille** combien d'électricité "
        "la France consommera le lendemain, heure par heure, pour prévoir assez de production. "
        "Nous avons construit et comparé plusieurs façons de faire cette prévision, avec 10 ans de "
        "données réelles (2016-2025), puis vérifié le résultat sur 2026."
    )

    st.subheader("Le problème en une image")
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, x1=13, y0=0.55, y1=0.95, fillcolor="#2a78d6", opacity=0.25, line_width=0)
    fig.add_shape(type="rect", x0=13, x1=24, y0=0.55, y1=0.95, fillcolor="#c2c1ba", opacity=0.35, line_width=0)
    fig.add_shape(type="rect", x0=24, x1=48, y0=0.55, y1=0.95, fillcolor="#eb6834", opacity=0.25, line_width=0)
    fig.add_shape(type="line", x0=14, x1=14, y0=0.3, y1=1.15, line=dict(color="#1f2933", width=3))
    for x, texte in [(6.5, "Jour J : consommation<br>et météo <b>connues</b><br>jusqu'à 13 h"),
                     (18.5, "Jour J après 13 h :<br><b>pas encore connu</b>"),
                     (36, "Jour J+1 : les <b>24 heures à prévoir</b>")]:
        fig.add_annotation(x=x, y=0.75, text=texte, showarrow=False, font=dict(size=13))
    fig.add_annotation(x=14, y=1.22, text="<b>14 h : on fait la prévision</b>", showarrow=False, font=dict(size=14))
    fig.update_xaxes(range=[0, 48], tickvals=[0, 6, 12, 14, 18, 24, 30, 36, 42, 48],
                     ticktext=["0 h", "6 h", "12 h", "14 h", "18 h", "0 h<br>J+1", "6 h", "12 h", "18 h", "24 h"])
    fig.update_yaxes(visible=False, range=[0.2, 1.3])
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white")
    st.plotly_chart(fig)
    st.caption(
        "Règle d'or du projet : ne jamais utiliser une information qui n'existait pas encore à 14 h. "
        "Des tests automatiques le vérifient : si on remplace tout ce qui arrive après 14 h par "
        "n'importe quoi, la prévision ne change pas."
    )

    st.subheader("Le résultat en trois chiffres")
    test = scores_periode("test")
    bonus = scores_periode("test_bonus")
    conso_moyenne = jours().loc["2024":"2025", "conso_moyenne_MW"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("Erreur moyenne de notre modèle (2024-2025)", mw(test.loc["M2", "MAE (MW)"]),
              help="En moyenne, sur chaque heure prévue, on se trompe de cette quantité (en plus ou en moins).")
    c2.metric("Soit, de la consommation", f"{100 * test.loc['M2', 'MAE (MW)'] / conso_moyenne:.1f} %".replace(".", ","),
              help=f"La France consomme en moyenne {mw(conso_moyenne)} sur 2024-2025.")
    c3.metric("Fois moins d'erreur que la méthode simple", f"{test.loc['B0', 'MAE (MW)'] / test.loc['M2', 'MAE (MW)']:.1f}".replace(".", ","),
              help="La méthode simple (B0) recopie la consommation la plus récente connue.")
    st.markdown(
        f"Pour se représenter : une erreur de {mw(test.loc['M2', 'MAE (MW)'])}, c'est à peu près la puissance "
        f"d'**un réacteur nucléaire** ({mw(REACTEUR_MW[0])} à {mw(REACTEUR_MW[1])}), sur une consommation "
        f"d'environ {mw(conso_moyenne)}. Sur 2026, des données que personne n'avait vues pendant le projet, "
        f"l'erreur est de {mw(bonus.loc['M2', 'MAE (MW)'])} : **le résultat tient**."
    )

    st.subheader("Comment lire ce tableau de bord")
    st.markdown(
        "- **Les données** : à quoi ressemble la consommation, et pourquoi la température compte.\n"
        "- **Explorer un jour** : choisissez une date et comparez la réalité aux prévisions.\n"
        "- **Qui gagne ?** : le classement des méthodes, et ce qui est vraiment significatif.\n"
        "- **Quand ça rate** : les saisons, jours et heures difficiles, et les pires journées expliquées.\n"
        "- **Un défaut commun** : pourquoi tous nos modèles prévoyaient un peu trop.\n"
        "- **Comment on a choisi** : ce que chaque ingrédient apporte.\n"
        "- **Limites** et **Lexique** : ce qu'il faut savoir avant de faire confiance, et les mots techniques."
    )


def page_donnees():
    st.title("Les données")
    en_une_phrase(
        "la consommation suit le calendrier (semaine, week-end, fériés, été) et surtout le froid : "
        "plus il fait froid, plus on chauffe, plus on consomme."
    )
    j = jours()
    st.subheader("Dix ans de consommation, jour par jour")
    fig = go.Figure()
    fig.add_scatter(x=j.index, y=j["conso_moyenne_MW"] / 1000, mode="lines", line=dict(color="#2a78d6", width=1),
                    name="moyenne du jour")
    for debut, fin, nom, couleur in [("2016-01-01", "2022-12-31", "apprentissage", "#2a78d6"),
                                     ("2023-01-01", "2023-12-31", "validation", "#eb6834"),
                                     ("2024-01-01", "2025-12-31", "test", "#7b4fd6"),
                                     ("2026-01-01", "2026-06-30", "bonus", "#1baf7a")]:
        fig.add_vrect(x0=debut, x1=fin, fillcolor=couleur, opacity=0.07, line_width=0,
                      annotation_text=nom, annotation_position="top left")
    st.plotly_chart(mise_en_page(fig, hauteur=360, unite="GW"))
    st.markdown(
        "On voit les **hivers** (haut) et les **étés** (bas), le creux du **confinement** au printemps 2020, "
        "et une consommation plus **basse depuis l'hiver 2022-2023**. Les modèles apprennent sur 2016-2022 "
        "(bleu), on choisit les réglages sur 2023 (orange), on juge sur 2024-2025 (violet), et on vérifie une "
        "dernière fois sur 2026 (vert)."
    )

    st.subheader("Le froid fait consommer")
    j2 = j.dropna(subset=["temperature_C", "conso_moyenne_MW"])
    ouvre = j2["type_jour"] == "ouvré"
    fig = go.Figure()
    fig.add_scatter(x=j2.loc[ouvre, "temperature_C"], y=j2.loc[ouvre, "conso_moyenne_MW"] / 1000, mode="markers",
                    marker=dict(size=4, color="#2a78d6", opacity=0.35), name="jours ouvrés")
    fig.add_scatter(x=j2.loc[~ouvre, "temperature_C"], y=j2.loc[~ouvre, "conso_moyenne_MW"] / 1000, mode="markers",
                    marker=dict(size=4, color="#eb6834", opacity=0.35), name="week-ends et fériés")
    fig.update_xaxes(title="température moyenne de la France (°C)")
    st.plotly_chart(mise_en_page(fig, hauteur=400, unite="GW (moyenne du jour)"))
    st.markdown(
        "Chaque point est un jour. **Sous 15 °C**, la consommation monte d'environ **2 400 MW par degré** "
        "en moins (chauffage électrique). Au-dessus de 22 °C, elle remonte un peu (climatisation). "
        "Les week-ends et fériés (orange) consomment moins que les jours ouvrés (bleu) à température égale. "
        "La relation n'est pas une ligne droite : c'est pourquoi nos modèles utilisent des « degrés de "
        "chauffage » (combien de degrés sous 15 °C)."
    )

    st.subheader("D'où viennent les données")
    st.markdown(
        "| Donnée | Source | Ce qu'on en tire |\n|---|---|---|\n"
        "| Consommation | RTE, éCO2mix (open data) | la consommation de la France, heure par heure |\n"
        "| Température | Météo-France, observations SYNOP de 40 stations | une température « France » pondérée par la consommation des régions |\n"
        "| Calendrier | jours fériés, ponts, vacances scolaires | le type de chaque jour à prévoir |"
    )


def page_jour():
    st.title("Explorer un jour")
    en_une_phrase("choisissez une date : on compare ce qui s'est vraiment passé à ce que chaque méthode avait prévu la veille à 14 h.")
    periode = choix_periode("periode_jour")
    p = previsions()
    p = p[p["periode"] == periode]
    dates = sorted(pd.to_datetime(p["jour_cible"].unique()))
    erreurs = erreurs_jour_periode(periode)
    m2 = erreurs[erreurs["methode"] == "M2"].set_index("jour")

    c1, c2 = st.columns([2, 1])
    with c2:
        raccourci = st.radio("Aller à", ["choisir une date", "le pire jour de M2", "le meilleur jour de M2"], key="raccourci")
    if raccourci == "le pire jour de M2":
        defaut = m2["mae"].idxmax()
    elif raccourci == "le meilleur jour de M2":
        defaut = m2["mae"].idxmin()
    else:
        defaut = dates[len(dates) // 2]
    with c1:
        jour = pd.Timestamp(st.date_input("Jour à prévoir (J+1)", value=defaut, min_value=dates[0], max_value=dates[-1],
                                          format="DD/MM/YYYY", disabled=raccourci != "choisir une date"))
    if jour not in set(dates):
        st.warning("Ce jour n'est pas noté (jour de changement d'heure, ou une méthode n'a pas ses 24 heures). Choisissez-en un autre.")
        return

    methodes = st.pills("Méthodes affichées", vis.METHODES, selection_mode="multi",
                        default=["B0", "M2", "Plafond"], format_func=lambda m: m)
    with st.expander("Que veut dire chaque méthode ?"):
        for m in vis.METHODES:
            st.markdown(f"- **{m}** : {DESCRIPTIONS[m]}")

    d = p[p["jour_cible"] == jour.strftime("%Y-%m-%d")].sort_values("heure")
    fig = go.Figure()
    fig.add_scatter(x=d["heure"], y=d["reel_MW"] / 1000, name="réalité", line=dict(color=COULEURS["reel_MW"], width=4))
    for m in methodes:
        fig.add_scatter(x=d["heure"], y=d[m] / 1000, name=m,
                        line=dict(color=COULEURS[m], width=2, dash="dash" if m == "Plafond" else "solid"))
    fig.update_xaxes(title="heure de la journée", tickvals=list(range(0, 24, 2)))
    infos = jours().loc[jour]
    veille = jours().loc[jour - pd.Timedelta(days=1)]
    titre = f"{JOURS_SEMAINE[jour.dayofweek].capitalize()} {jour:%d/%m/%Y} ({infos['type_jour']})"
    st.plotly_chart(mise_en_page(fig, titre, hauteur=420, unite="GW"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Température ce jour-là", f"{infos['temperature_C']:.1f} °C".replace(".", ","))
    c2.metric("Température la veille", f"{veille['temperature_C']:.1f} °C".replace(".", ","),
              delta=f"{infos['temperature_C'] - veille['temperature_C']:+.1f} °C d'écart".replace(".", ","), delta_color="off")
    c3.metric("Erreur moyenne de M2 ce jour", mw(m2.loc[jour, "mae"]))
    e = erreurs[erreurs["jour"] == jour].set_index("methode")
    tableau = pd.DataFrame({
        "erreur moyenne (MW)": e["mae"].round(0),
        "erreur sur la pointe (MW)": e["erreur_pointe"].round(0),
        "écart sur l'heure de pointe (h)": e["ecart_heure_pointe"],
    }).loc[vis.METHODES]
    st.dataframe(tableau, width="stretch")
    st.caption("Erreur sur la pointe : positive si on a prévu un maximum trop haut.")


def page_classement():
    st.title("Qui gagne ?")
    en_une_phrase(
        "tous nos modèles font au moins deux fois mieux que les méthodes simples ; M2 (avec la température) "
        "est le meilleur des modèles utilisables, à égalité avec M3, mais plus simple."
    )
    periode = choix_periode("periode_classement")
    s = scores_periode(periode)
    st.caption(f"{int(s['nb_jours'].iloc[0])} jours, les mêmes pour toutes les méthodes.")
    mae = s["MAE (MW)"]
    fig = go.Figure(go.Bar(
        x=mae.values, y=mae.index, orientation="h", marker_color=[COULEURS[m] for m in mae.index],
        text=[mw(v) for v in mae.values], textposition="outside",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="erreur moyenne par heure (MW) : plus c'est court, mieux c'est", range=[0, mae.max() * 1.2])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), separators=", ")
    st.plotly_chart(fig)

    tableau = pd.DataFrame({
        "ce que fait la méthode": [DESCRIPTIONS[m] for m in s.index],
        "erreur moyenne (MW)": s["MAE (MW)"].round(0),
        "erreur en %": s["MAPE (%)"].round(1),
        "biais (MW)": s["biais (MW)"].round(0),
        "erreur sur l'énergie du jour (GWh)": s["erreur énergie du jour (GWh, absolue)"].round(1),
        "erreur sur la pointe (MW)": s["erreur pointe (MW, absolue)"].round(0),
        "heure de pointe exacte (% des jours)": s["heure de pointe exacte (% des jours)"].round(0),
    })
    st.dataframe(tableau, width="stretch")

    st.subheader("Les écarts sont-ils réels, ou dus au hasard ?")
    nom = {"validation": "significativite_2023", "test": "significativite_2024_2025",
           "test_bonus": "test_bonus_2026_significativite"}[periode]
    t = lire(nom)
    t = t[t["perte"] == "MAE"].assign(methode=lambda x: x["autre_methode"].map(vis.NOMS_COURTS))
    phrases = []
    for _, ligne in t.iterrows():
        part = f"{100 * ligne['part_jours_reference_meilleure']:.0f} %"
        if ligne["conclusion"] == "écart non significatif":
            phrases.append(f"- **M2 et {ligne['methode']} : égalité.** M2 fait mieux {part} des jours ; l'écart peut s'expliquer par le hasard (p = {ligne['p_valeur']:.2f}).".replace("0.", "0,"))
        elif ligne["conclusion"] == "référence meilleure":
            phrases.append(f"- **M2 bat {ligne['methode']}** pour de bon (M2 meilleur {part} des jours).")
        else:
            phrases.append(f"- **{ligne['methode']} bat M2** pour de bon (M2 meilleur seulement {part} des jours).")
    st.markdown("\n".join(phrases))
    st.caption("Test de Diebold-Mariano sur l'erreur de chaque jour. « Pour de bon » : p-valeur inférieure à 0,05.")


def page_echecs():
    st.title("Quand ça rate, et pourquoi")
    en_une_phrase(
        "les erreurs sont plus grandes en hiver, par grand froid, les jours fériés et l'après-midi ; "
        "les pires journées sont surtout des redoux soudains que notre modèle ne pouvait pas voir venir."
    )
    periode = choix_periode("periode_echecs")
    erreurs = erreurs_jour_periode(periode)
    methodes = st.pills("Méthodes", vis.METHODES, selection_mode="multi", default=["B0", "M2", "M3", "Plafond"],
                        key="methodes_echecs")
    erreurs = erreurs.assign(
        classe_temperature=pd.cut(erreurs["temperature_C"], [-np.inf, 5, 10, 15, 20, np.inf],
                                  labels=["moins de 5 °C", "5 à 10 °C", "10 à 15 °C", "15 à 20 °C", "plus de 20 °C"]),
        jour_semaine_nom=erreurs["jour"].dt.dayofweek.map(dict(enumerate(JOURS_SEMAINE))),
    )

    def barres(critere, ordre, titre):
        t = erreurs[erreurs["methode"].isin(methodes)].groupby([critere, "methode"], observed=True)["mae"].mean().unstack()
        t = t.reindex([o for o in ordre if o in t.index])
        nb = erreurs[erreurs["methode"] == "M2"].groupby(critere, observed=True).size()
        fig = go.Figure()
        for m in methodes:
            fig.add_bar(x=[f"{g}<br>({nb.get(g, 0)} j)" for g in t.index], y=t[m], name=m, marker_color=COULEURS[m])
        st.plotly_chart(mise_en_page(fig, titre, hauteur=340))

    c1, c2 = st.columns(2)
    with c1:
        barres("saison", ["hiver", "printemps", "été", "automne"], "Par saison")
    with c2:
        barres("classe_temperature", ["moins de 5 °C", "5 à 10 °C", "10 à 15 °C", "15 à 20 °C", "plus de 20 °C"],
               "Par température du jour")
    c1, c2 = st.columns(2)
    with c1:
        barres("type_jour", ["ouvré", "week-end", "pont", "férié", "Noël"], "Par type de jour")
    with c2:
        barres("jour_semaine_nom", JOURS_SEMAINE, "Par jour de la semaine")

    p = previsions()
    p = p[p["periode"] == periode]
    fig = go.Figure()
    for m in methodes:
        fig.add_scatter(x=list(range(24)), y=(p[m] - p["reel_MW"]).abs().groupby(p["heure"]).mean(), name=m,
                        line=dict(color=COULEURS[m]), mode="lines+markers")
    fig.add_vline(x=12.5, line_dash="dot", line_color="#888")
    fig.add_annotation(x=12.6, y=1, yref="paper", text="après 12 h : la veille n'est pas encore connue à 14 h",
                       showarrow=False, xanchor="left", font=dict(size=11))
    fig.update_xaxes(title="heure de la journée", tickvals=list(range(0, 24, 2)))
    st.plotly_chart(mise_en_page(fig, "Par heure de la journée", hauteur=340))
    st.markdown(
        "L'erreur saute à 13 h : pour prévoir l'après-midi de demain, on ne connaît pas encore la consommation "
        "d'aujourd'hui à la même heure (elle n'est publiée qu'après 14 h). Les nuits sont les plus faciles."
    )

    st.subheader("Les 5 pires journées de M2, expliquées")
    m2 = erreurs[erreurs["methode"] == "M2"].set_index("jour")
    plafond = erreurs[erreurs["methode"] == "Plafond"].set_index("jour")["mae"]
    lignes = []
    for jour in m2["mae"].nlargest(5).index:
        temp, temp_veille = jours().loc[jour, "temperature_C"], jours().loc[jour - pd.Timedelta(days=1), "temperature_C"]
        sens = "trop haut" if m2.loc[jour, "biais"] > 0 else "trop bas"
        if plafond[jour] < 0.5 * m2.loc[jour, "mae"]:
            cause = (f"Changement brusque de température ({temp_veille:.0f} °C la veille, {temp:.0f} °C ce jour) : "
                     f"avec la vraie météo, l'erreur tombe à {mw(plafond[jour])}. Il manquait une prévision météo.")
        elif m2.loc[jour, "type_jour"] in ("férié", "pont", "Noël"):
            cause = "Jour spécial du calendrier, que le modèle connaît mal (peu d'exemples pour apprendre)."
        else:
            cause = "Ni la météo ni le calendrier ne l'expliquent : cause à chercher ailleurs."
        lignes.append({
            "jour": f"{JOURS_SEMAINE[jour.dayofweek]} {jour:%d/%m/%Y}",
            "erreur moyenne": mw(m2.loc[jour, "mae"]),
            "M2 a prévu": sens,
            "explication": cause,
        })
    st.dataframe(pd.DataFrame(lignes), width="stretch", hide_index=True)
    st.caption("Explication automatique : « changement de température » si la vraie météo (plafond) divise l'erreur au moins par deux. "
               "Pour voir la courbe d'un de ces jours : page « Explorer un jour ».")


def page_biais():
    st.title("Un défaut commun : les modèles prévoyaient trop")
    en_une_phrase(
        "depuis 2023, la France consomme moins qu'avant à météo égale ; nos modèles, qui ont appris sur "
        "2016-2022, prévoyaient donc un peu trop, puis ont rattrapé ce retard en 2026."
    )
    p = previsions()
    p = p.assign(mois=p["jour_cible"].str[:7])
    biais = pd.DataFrame({m: (p[m] - p["reel_MW"]).groupby(p["mois"]).mean() for m in ["B0", "M2", "Plafond"]})
    fig = go.Figure()
    for m in biais.columns:
        fig.add_scatter(x=biais.index, y=biais[m], name=m, mode="lines+markers", line=dict(color=COULEURS[m]))
    fig.add_hline(y=0, line_color="#1f2933")
    fig.update_yaxes(title="biais moyen (MW) : au-dessus de 0 = on prévoit trop")
    st.plotly_chart(mise_en_page(fig, hauteur=400, unite="MW"))
    resume = p.groupby("periode")[["M2", "reel_MW"]].apply(lambda d: (d["M2"] - d["reel_MW"]).mean())
    c1, c2, c3 = st.columns(3)
    for colonne, (periode, titre) in zip((c1, c2, c3), vis.PERIODES.items()):
        colonne.metric(f"Biais moyen de M2, {titre.lower()}", f"{resume[periode]:+,.0f} MW".replace(",", " "))
    st.markdown(
        "- La méthode simple B0 (gris) n'a presque pas ce défaut : elle recopie les jours récents, elle suit donc le niveau.\n"
        "- Le plafond (vert), qui connaît la vraie météo, l'a aussi : **ce n'est donc pas la météo**.\n"
        "- Notre explication (une hypothèse) : la **sobriété énergétique** depuis la crise de l'énergie de 2022. "
        "Les modèles apprennent sur des années où l'on consommait plus. Comme ils réapprennent chaque mois avec "
        "les données récentes, le biais diminue : il est presque nul en 2026.\n"
        "- Nous ne l'avons **pas corrigé**, car nous l'avons découvert sur les données de test : corriger après "
        "coup reviendrait à tricher. C'est la première amélioration à faire."
    )


def page_choix():
    st.title("Comment on a choisi")
    en_une_phrase(
        "tous les choix ont été faits sur l'année 2023 seulement ; les années 2024-2026 n'ont servi qu'à juger, "
        "pour ne pas se tromper soi-même."
    )

    def barres(t, x, y, titre, couleur="#2a78d6", retenu=None):
        couleurs = ["#eb6834" if retenu is not None and v == retenu else couleur for v in t[y]]
        fig = go.Figure(go.Bar(x=t[x], y=t[y], orientation="h", marker_color=couleurs,
                               text=[mw(v) for v in t[x]], textposition="outside"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="erreur moyenne en 2023 (MW)", range=[0, t[x].max() * 1.25])
        fig.update_layout(title=titre, height=60 + 45 * len(t), margin=dict(l=10, r=10, t=40, b=10), separators=", ")
        st.plotly_chart(fig)

    st.subheader("1. La consommation passée : l'ingrédient le plus important")
    lags = lire("ablation_lags_m1_2023").assign(nom=lambda d: d["variante"].map({
        "LAG-A": "veille (matin) + semaine passée", "LAG-B": "veille (matin) + avant-veille + semaine passée",
        "LAG-C": "avant-veille + semaine passée", "LAG-D": "semaine passée seulement"}))
    barres(lags, "MAE_MW", "nom", "Quelles consommations passées utiliser ?",
           retenu="veille (matin) + avant-veille + semaine passée")
    st.caption("Sans la consommation de la veille et de l'avant-veille, l'erreur double. En orange : le choix retenu.")

    st.subheader("2. La température : le froid compte, mais pas en ligne droite")
    meteo = lire("ablation_m2_2023")
    v = meteo[meteo["candidat_temperature"] == "temp_38_ponderee"].assign(nom=lambda d: d["variante_meteo"].map({
        "M2-A": "température de 13 h seule", "M2-B": "+ température de la veille", "M2-C": "+ température lissée",
        "M2-D": "13 h, lissée, degrés de chauffage", "M2-E": "+ degrés de climatisation", "M2-F": "toutes (7 variables)"}))
    barres(v, "MAE_MW", "nom", "Quelles informations de température ?", retenu="toutes (7 variables)")
    t = meteo[meteo["variante_meteo"] == "M2-F"]
    st.markdown(
        "Trois façons de calculer « la température de la France » ont été comparées : "
        + ", ".join(f"**{n}** {mw(m)}" for n, m in zip(t["candidat_temperature"], t["MAE_MW"]))
        + ". **C'est une égalité** (moins de 1 MW d'écart) : nous avons gardé la moyenne pondérée par la "
          "consommation des régions, la plus logique."
    )

    st.subheader("3. Un modèle par heure, ou un seul ?")
    d14 = lire("decision14_un_modele_contre_24_2023")
    barres(d14, "MAE_MW", "forme", "Une régression pour chaque heure, ou une seule pour les 24 ?",
           retenu="24 modèles (un par heure)")
    st.caption("Avec un seul modèle, l'effet du lundi ou du froid serait le même à 4 h et à 19 h : c'est faux.")

    st.subheader("4. Faut-il enlever le confinement de 2020 ?")
    covid = lire("sensibilite_covid_2023")
    covid = covid.assign(nom=lambda d: d["modele"] + np.where(d["confinement_retire"], " : sans le confinement (choix fait)",
                                                             " : avec le confinement"))
    barres(covid, "MAE_MW", "nom", "Erreur en 2023")
    st.markdown(
        "Nous avions décidé de retirer les jours du confinement, et promis de vérifier. La vérification, faite "
        "trop tard, nous donne tort : les garder aurait été meilleur. Nous le disons honnêtement, sans changer "
        "le modèle après coup."
    )


def page_limites():
    st.title("Limites, et ce qu'on améliorerait")
    en_une_phrase("notre modèle est fiable la plupart du temps, mais il faut savoir quand s'en méfier.")
    st.subheader("Quand ne pas faire confiance au modèle")
    st.markdown(
        "- **Les changements brusques de température** : il ne connaît que la température observée jusqu'à 13 h, "
        "pas la prévision météo du lendemain.\n"
        "- **Les jours de fin d'année, les fériés**, surtout un férié qui tombe un week-end : peu d'exemples pour apprendre.\n"
        "- **Les périodes où la consommation change de niveau** (crise de l'énergie) : il met du temps à s'adapter."
    )
    st.subheader("Ce que nous disons honnêtement")
    st.markdown(
        "- Le test 2024-2025 du modèle M2 a été lancé **avant** que M3 et M4 soient construits : leurs réglages viennent "
        "de 2023, mais nous connaissions déjà le score de M2.\n"
        "- Le modèle M4 utilisait par erreur une heure pas encore publiée à 14 h. L'erreur a été trouvée, corrigée, et son test relancé.\n"
        "- Les données de consommation sont les versions définitives de RTE, un peu plus propres que celles disponibles "
        "le jour même à 14 h : nos erreurs sont probablement un peu optimistes.\n"
        "- Le test bonus 2026 ne couvre que 6 mois (hiver et printemps)."
    )
    st.subheader("Ce qui améliorerait le plus la prévision")
    test = scores_periode("test")
    st.markdown(
        f"1. **Une prévision météo du lendemain** : avec la vraie météo, l'erreur passerait de "
        f"{mw(test.loc['M2', 'MAE (MW)'])} à {mw(test.loc['Plafond', 'MAE (MW)'])}.\n"
        "2. **Suivre le niveau récent de consommation** (une tendance, ou plus de poids aux années récentes).\n"
        "3. **Traiter à part les jours spéciaux** : veille de Noël, fériés du week-end."
    )


def page_lexique():
    st.title("Lexique")
    en_une_phrase("les mots techniques du projet, expliqués simplement.")
    mots = {
        "MW (mégawatt)": "Unité de puissance. La France consomme en moyenne environ 50 000 MW ; un réacteur nucléaire produit 900 à 1 450 MW.",
        "GW (gigawatt)": "1 GW = 1 000 MW.",
        "Erreur moyenne (MAE)": "On regarde, pour chaque heure prévue, de combien on s'est trompé (sans tenir compte du sens), puis on fait la moyenne.",
        "RMSE": "Une autre erreur moyenne, qui punit plus fort les grosses erreurs.",
        "Biais": "L'erreur moyenne avec son signe : positive si on prévoit trop en moyenne, négative si on prévoit trop peu.",
        "Pointe": "Le moment de la journée où la consommation est la plus forte (souvent vers 19 h en hiver).",
        "Benchmark (B0, B1, B2)": "Méthode très simple, sans apprentissage, qui sert de point de comparaison : un modèle doit faire mieux pour être utile.",
        "Modèle (M1 à M4)": "Méthode qui apprend des années passées comment la consommation dépend du calendrier, de la météo et des jours précédents.",
        "Régression linéaire": "Le modèle le plus simple qui apprend : la prévision est une somme d'effets (effet du lundi + effet du froid + ...).",
        "Gradient boosting (M3)": "Modèle d'apprentissage automatique qui combine beaucoup de petits arbres de décision « si... alors... ».",
        "Plafond « météo parfaite »": "Le même modèle, mais avec la vraie météo du lendemain. Impossible en vrai : il montre le gain qu'apporterait une prévision météo parfaite.",
        "Apprentissage, validation, test": "On apprend sur 2016-2022, on choisit les réglages sur 2023, on juge sur 2024-2025 sans plus rien changer, puis une dernière fois sur 2026.",
        "Fuite d'information": "Utiliser par erreur une information du futur (par exemple la météo du lendemain) : la prévision paraît meilleure qu'elle ne l'est. Des tests automatiques l'empêchent.",
        "Significatif (p-valeur)": "Un écart est « significatif » s'il est trop grand pour être dû au hasard (p-valeur inférieure à 0,05).",
        "Degrés de chauffage": "Combien de degrés il fait sous 15 °C : 0 s'il fait plus de 15 °C, 5 s'il fait 10 °C. Mesure le besoin de chauffer.",
    }
    for mot, definition in mots.items():
        st.markdown(f"**{mot}** : {definition}")


# ===========================================================================
# Navigation
# ===========================================================================

def main():
    st.set_page_config(page_title="Prévision de la consommation électrique", page_icon="⚡", layout="wide")
    if not (RESULTATS / "visualisation_previsions.csv").exists():
        st.error("Fichiers absents : lancer d'abord `python -m src.visualisation` (voir le README).")
        st.stop()
    pages = {
        "Comprendre": [
            st.Page(page_accueil, title="Le projet en bref", icon="⚡", default=True),
            st.Page(page_donnees, title="Les données", icon="📈", url_path="donnees"),
            st.Page(page_jour, title="Explorer un jour", icon="📅", url_path="jour"),
        ],
        "Résultats": [
            st.Page(page_classement, title="Qui gagne ?", icon="🏆", url_path="classement"),
            st.Page(page_echecs, title="Quand ça rate", icon="🔍", url_path="echecs"),
            st.Page(page_biais, title="Un défaut commun", icon="⚖️", url_path="biais"),
            st.Page(page_choix, title="Comment on a choisi", icon="🧪", url_path="choix"),
        ],
        "Pour aller plus loin": [
            st.Page(page_limites, title="Limites", icon="⚠️", url_path="limites"),
            st.Page(page_lexique, title="Lexique", icon="📖", url_path="lexique"),
        ],
    }
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
