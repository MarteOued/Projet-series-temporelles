"""Tableau de bord : la visite guidée du projet, claire pour tout le monde.

Lancer depuis la racine du projet :
    streamlit run app/tableau_de_bord.py

Il ne calcule aucun modèle : il lit les fichiers de data/resultats/ (versionnés),
préparés par les commandes du README. Les scores viennent de src/evaluation.py :
ce sont les mêmes chiffres que dans le rapport et le notebook 04.

Organisation
------------
- composants.py : style, couleurs fixes des méthodes, cartes, mise en forme des graphiques ;
- contenu.py    : textes des fiches des méthodes et du lexique ;
- ce fichier    : les pages et la navigation.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DOSSIER_APP = Path(__file__).resolve().parent
RACINE = DOSSIER_APP.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(DOSSIER_APP))

import composants as ui  # noqa: E402
import contenu  # noqa: E402
from src import visualisation as vis  # noqa: E402

RESULTATS = RACINE / "data" / "resultats"
JOURS_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MODELES = ["M1", "M2", "M3", "M4"]
PAGES = {}   # rempli par main() : permet les liens entre pages


# ===========================================================================
# Données (lues une fois, gardées en mémoire)
# ===========================================================================
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
    """Erreurs quotidiennes de chaque méthode, avec la description de chaque jour."""
    p = previsions()
    p = p[p["periode"] == periode]
    morceaux = []
    for m in vis.METHODES:
        e = vis.erreurs_quotidiennes(p, m)
        e["methode"] = m
        morceaux.append(e)
    return pd.concat(morceaux).rename_axis("jour").reset_index().join(jours(), on="jour")


def periode_courante():
    return st.session_state.get("periode", "test")


def _changer_periode():
    st.session_state["periode"] = st.session_state["_choix_periode"]


def rappel_periode():
    """Le choix de la période, en haut de chaque page de résultats (partagé entre les pages)."""
    periode = periode_courante()
    st.segmented_control(
        "Période", list(vis.PERIODES), format_func=vis.PERIODES.get, default=periode, key="_choix_periode",
        required=True, on_change=_changer_periode, label_visibility="collapsed",
        help="Validation 2023 : on y a choisi les réglages · Test 2024-2025 : le juge final · Bonus 2026 : un dernier examen",
    )
    st.caption(f"{int(scores_periode(periode)['nb_jours'].iloc[0])} jours notés, les mêmes pour toutes les méthodes.")


def lien(page, texte):
    if page in PAGES:
        st.page_link(PAGES[page], label=texte, icon=":material/arrow_forward:")


def date_fr(jour):
    jour = pd.Timestamp(jour)
    return f"{JOURS_SEMAINE[jour.dayofweek]} {jour.day} {MOIS[jour.month - 1]} {jour.year}"


# ===========================================================================
# 1. Accueil
# ===========================================================================
def page_accueil():
    ui.entete(
        "Projet de séries temporelles · Master 1 Data Science · Université Lyon 2",
        "Prévoir la consommation d'électricité de la France, la veille pour le lendemain",
        "Chaque jour à 14 h, le gestionnaire du réseau électrique doit savoir combien d'électricité le pays "
        "consommera le lendemain, heure par heure. Nous avons construit, comparé et vérifié plusieurs façons "
        "de faire cette prévision, sur dix ans de données réelles.",
    )
    test, bonus = scores_periode("test"), scores_periode("test_bonus")
    conso = jours().loc["2024":"2025", "conso_moyenne_MW"].mean()
    m2 = test.loc["M2", "MAE (MW)"]
    st.markdown(
        f'<div class="heros"><div><div class="chiffre">{ui.nombre(100 * m2 / conso)} %</div>'
        f'<div class="sous">d\'erreur moyenne sur chaque heure prévue, 2024-2025</div></div>'
        f'<div class="texte">Notre modèle retenu, <b>M2</b>, se trompe en moyenne de <b>{ui.mw(m2)}</b> par heure, '
        f'sur une consommation moyenne de {ui.mw(conso)}. C\'est à peu près la puissance d\'<b>un réacteur nucléaire</b> '
        f'(900 à 1 450 MW). Il fait <b>{ui.nombre(test.loc["B0", "MAE (MW)"] / m2)} fois mieux</b> que la méthode simple '
        f'qui recopie la veille, et le résultat tient sur six mois de 2026 que personne n\'avait vus.</div></div>',
        unsafe_allow_html=True,
    )
    ui.tuiles([
        ("Erreur de M2, 2024-2025", ui.mw(m2), "le test final, lancé une fois les choix gelés"),
        ("Erreur de M2, début 2026", ui.mw(bonus.loc["M2", "MAE (MW)"]), "un dernier examen sur des données neuves"),
        ("Méthode simple (B0)", ui.mw(test.loc["B0", "MAE (MW)"]), "recopier la consommation la plus récente"),
        ("Avec une météo parfaite", ui.mw(test.loc["Plafond", "MAE (MW)"]), "ce qu'apporterait une prévision météo"),
    ])

    st.subheader("Le classement en un coup d'œil")
    mae = test["MAE (MW)"].sort_values()
    fig = go.Figure(go.Bar(
        x=mae.values, y=[ui.NOMS_LONGS[m] for m in mae.index], orientation="h",
        marker=dict(color=[ui.COULEURS[m] for m in mae.index], line=dict(color=ui.SURFACE, width=2)),
        text=[ui.texte_barre(v) for v in mae.values], textposition="outside", textfont=dict(color=ui.ENCRE),
        hovertemplate="%{y} : %{x:,.0f} MW<extra></extra>", cliponaxis=False,
    ))
    fig.update_yaxes(autorange="reversed")
    ui.mise_en_forme(fig, hauteur=360, titre_x="erreur moyenne par heure, 2024-2025 (MW) · plus la barre est courte, mieux c'est",
                     legende=False)
    fig.update_xaxes(range=[0, mae.max() * 1.18])
    ui.marge_etiquettes(fig, [ui.NOMS_LONGS[m] for m in mae.index])
    ui.afficher(fig)
    st.markdown(
        '<p class="petit">En gris, les trois benchmarks qui ne font que recopier le passé. Le plafond (vert d\'eau) '
        "n'est pas une vraie prévision : il connaît la météo réelle du lendemain et sert de repère.</p>",
        unsafe_allow_html=True,
    )

    st.subheader("Par où commencer")
    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        st.markdown("**Comprendre le problème**  \nLa règle des 14 h, les périodes, le chemin des données.")
        lien("methode", "La méthode")
    with c2, st.container(border=True):
        st.markdown("**Connaître les modèles**  \nUne fiche par méthode : ce qu'elle sait, comment elle apprend.")
        lien("modeles", "Les modèles")
    with c3, st.container(border=True):
        st.markdown("**Voir une vraie journée**  \nLa réalité contre les prévisions, jour par jour.")
        lien("jour", "Explorer un jour")


# ===========================================================================
# 2. La méthode
# ===========================================================================
def page_methode():
    ui.entete("Comprendre", "La méthode",
              "Une prévision n'a de valeur que si elle aurait vraiment pu être faite à l'heure dite. Tout le projet "
              "est construit autour de cette règle, et vérifié par des tests automatiques.")
    ui.en_une_phrase("à 14 h le jour J, on ne s'autorise que ce qui est déjà publié, et on juge les modèles sur des "
                     "années qu'ils n'ont jamais vues.")

    st.subheader("La règle des 14 h, heure par heure")
    cellules = []
    for h in range(48):
        if h < 13:
            couleur, titre = "rgba(42,120,214,0.55)", f"jour J, {h} h : connu"
        elif h < 24:
            couleur, titre = ui.GRILLE, f"jour J, {h} h : pas encore publié à 14 h"
        else:
            couleur, titre = "rgba(235,104,52,0.55)", f"lendemain, {h - 24} h : à prévoir"
        cellules.append(f'<div title="{titre}" style="background:{couleur}"></div>')
    st.markdown(
        f'<div class="horloge">{"".join(cellules)}</div>'
        '<div class="legende-horloge">'
        '<span><span class="pastille" style="background:rgba(42,120,214,0.75)"></span>Jour J, 0 h à 13 h : consommation et météo connues</span>'
        f'<span><span class="pastille" style="background:{ui.GRILLE}"></span>Jour J après 13 h : pas encore publié</span>'
        '<span><span class="pastille" style="background:rgba(235,104,52,0.75)"></span>Lendemain : les 24 heures à prévoir</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "La consommation de la tranche 13 h-14 h se termine à 14 h pile : elle n'est **pas** encore publiée. "
        "Pour prévoir l'après-midi du lendemain, le modèle ne connaît donc que l'avant-veille à la même heure. "
        "La météo est prise jusqu'à la dernière observation de 13 h au plus tard."
    )

    st.subheader("Quatre périodes, quatre rôles")
    periodes = [("Apprentissage", "2016-01-01", "2023-01-01", "les modèles apprennent", ui.RAMPE_BLEUE[2]),
                ("Validation", "2023-01-01", "2024-01-01", "on choisit les réglages", ui.RAMPE_BLEUE[3]),
                ("Test final", "2024-01-01", "2026-01-01", "on juge, sans rien changer", ui.RAMPE_BLEUE[5]),
                ("Test bonus", "2026-01-01", "2026-07-01", "un dernier examen", ui.RAMPE_BLEUE[6])]
    fig = go.Figure()
    for nom, debut, fin, role, couleur in periodes:
        d0, d1 = pd.Timestamp(debut), pd.Timestamp(fin)
        fig.add_trace(go.Bar(
            x=[(d1 - d0).days * 86_400_000], base=[d0], y=[f"<b>{nom}</b><br><span style='font-size:12px'>{role}</span>"],
            orientation="h", marker=dict(color=couleur), name=nom,
            hovertemplate=f"{nom} : {d0:%d/%m/%Y} → {(d1 - pd.Timedelta(days=1)):%d/%m/%Y}<extra></extra>",
        ))
    fig.add_vrect(x0="2020-03-17", x1="2020-05-18", fillcolor=ui.COULEURS["M3"], opacity=0.25, line_width=0)
    fig.add_annotation(x="2020-04-15", y=1.08, yref="paper", text="confinement : retiré de l'apprentissage",
                       showarrow=False, font=dict(size=12, color=ui.ENCRE_2))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(type="date")
    ui.mise_en_forme(fig, hauteur=290, legende=False)
    ui.marge_etiquettes(fig, ["les modèles apprennent", "on juge, sans rien changer"])
    fig.update_layout(margin=dict(t=36))
    ui.afficher(fig)
    st.markdown("Au début de **chaque mois**, les modèles réapprennent avec toutes les données disponibles jusque-là : "
                "comme le ferait un vrai service de prévision. Le test 2024-2025 n'a servi à choisir aucun réglage.")

    st.subheader("Le chemin des données")
    etapes = [
        ("1", "Télécharger", "consommation RTE, météo Météo-France, calendrier", "rte.py, meteo.py"),
        ("2", "Nettoyer", "heures manquantes, stations en panne, valeurs aberrantes", "pipeline_meteo.py"),
        ("3", "Variables à 14 h", "seulement ce qui est connu à 14 h la veille", "features.py"),
        ("4", "Modèles", "B0 à B2, M1 à M4, plafond, réappris chaque mois", "experiences.py"),
        ("5", "Noter", "mêmes jours, mêmes mesures pour tous", "comparaison.py"),
        ("6", "Comprendre", "saisons, jours spéciaux, pires journées", "analyses.py"),
    ]
    st.markdown('<div class="flux">' + "".join(
        f'<div class="etape"><div class="num">ÉTAPE {n}</div><div class="nom">{nom}</div>'
        f'<div class="quoi">{quoi}</div><div class="quoi"><code>{fichier}</code></div></div>'
        for n, nom, quoi, fichier in etapes) + "</div>", unsafe_allow_html=True)

    st.subheader("Comment on vérifie qu'on ne triche pas")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Le test de non-fuite.** On remplace par des valeurs absurdes tout ce qui arrive après 14 h, "
                    "puis on reconstruit les variables : elles ne doivent pas bouger d'un chiffre. Le test a été "
                    "lui-même vérifié en introduisant exprès deux fausses fuites : il les attrape.")
    with c2, st.container(border=True):
        st.markdown("**Le futur ne change pas le passé.** Ajouter six mois de 2026 aux données laisse les données "
                    "et les variables de 2016-2025 identiques à l'octet près : aucun traitement ne regarde le futur. "
                    "Plus de 500 tests automatiques tournent à chaque modification.")


# ===========================================================================
# 3. Les données
# ===========================================================================
def page_donnees():
    ui.entete("Comprendre", "Les données",
              "Dix ans de consommation électrique nationale, de températures et de calendrier. "
              "Deux choses expliquent presque tout : le calendrier et le froid.")
    ui.en_une_phrase("la consommation suit le rythme de la semaine et des saisons, et surtout le froid : plus il fait "
                     "froid, plus on chauffe, plus on consomme.")
    j = jours()
    st.subheader("Dix ans de consommation, jour par jour")
    fig = go.Figure(go.Scatter(x=j.index, y=j["conso_moyenne_MW"] / 1000, mode="lines", name="consommation",
                               line=dict(color=ui.BLEU, width=1.2),
                               hovertemplate="%{x|%d/%m/%Y} : %{y:.1f} GW<extra></extra>"))
    for debut, fin, nom in [("2023-01-01", "2023-12-31", "validation"), ("2024-01-01", "2025-12-31", "test"),
                            ("2026-01-01", "2026-06-30", "bonus")]:
        fig.add_vrect(x0=debut, x1=fin, fillcolor=ui.ENCRE, opacity=0.04, line_width=0,
                      annotation_text=nom, annotation_position="top left", annotation_font=dict(color=ui.ENCRE_2))
    fig.add_annotation(x="2020-04-15", y=j.loc["2020-04", "conso_moyenne_MW"].min() / 1000, text="confinement",
                       showarrow=True, arrowcolor=ui.DISCRET, ax=0, ay=40, font=dict(color=ui.ENCRE_2, size=12))
    fig.add_annotation(x="2023-01-15", y=j.loc["2023-01", "conso_moyenne_MW"].max() / 1000,
                       text="sobriété : hivers plus bas", showarrow=True, arrowcolor=ui.DISCRET, ax=0, ay=-35,
                       font=dict(color=ui.ENCRE_2, size=12))
    ui.mise_en_forme(fig, hauteur=360, unite_y="GW (moyenne du jour)", legende=False)
    ui.afficher(fig)

    c1, c2 = st.columns([3, 2])
    with c1:
        j2 = j.dropna(subset=["temperature_C", "conso_moyenne_MW"])
        ouvre = j2["type_jour"] == "ouvré"
        fig = go.Figure()
        for masque, nom, couleur in [(ouvre, "jours ouvrés", ui.BLEU), (~ouvre, "week-ends et fériés", ui.COULEURS["M3"])]:
            fig.add_trace(go.Scatter(
                x=j2.loc[masque, "temperature_C"], y=j2.loc[masque, "conso_moyenne_MW"] / 1000, mode="markers", name=nom,
                marker=dict(size=5, color=couleur, opacity=0.4, line=dict(width=0)),
                hovertemplate="%{x:.1f} °C : %{y:.1f} GW<extra></extra>"))
        fig.add_vline(x=15, line=dict(color=ui.DISCRET, dash="dot", width=1))
        fig.add_annotation(x=15, y=1, yref="paper", text=" 15 °C : le chauffage s'arrête", showarrow=False,
                           xanchor="left", font=dict(size=12, color=ui.ENCRE_2))
        ui.mise_en_forme(fig, "Le froid fait consommer", hauteur=400, unite_y="GW (moyenne du jour)",
                         titre_x="température moyenne de la France (°C)")
        ui.afficher(fig)
    with c2:
        st.markdown("#### Ce que montre ce nuage")
        st.markdown(
            "- Chaque point est **un jour**.\n"
            "- **Sous 15 °C**, la consommation monte d'environ **2 400 MW par degré** de moins : le chauffage électrique.\n"
            "- **Au-dessus de 22 °C**, elle remonte un peu : la climatisation.\n"
            "- À température égale, les **week-ends et fériés** (orange) consomment moins.\n"
            "- La relation n'est pas une ligne droite : les modèles utilisent donc des **degrés de chauffage** "
            "(combien de degrés sous 15 °C)."
        )
    st.subheader("D'où viennent les données")
    st.markdown(
        '<table class="propre"><tr><th>Donnée</th><th>Source</th><th>Ce qu\'on en tire</th></tr>'
        "<tr><td>Consommation</td><td>RTE, éCO2mix (données ouvertes)</td><td>la consommation de la France, heure par heure</td></tr>"
        "<tr><td>Température</td><td>Météo-France, observations SYNOP, 40 stations</td><td>une température « France », pondérée par la consommation des régions</td></tr>"
        "<tr><td>Calendrier</td><td>jours fériés, ponts, vacances scolaires</td><td>le type de chaque jour à prévoir</td></tr></table>",
        unsafe_allow_html=True,
    )


# ===========================================================================
# 4. Les modèles
# ===========================================================================
def page_modeles():
    ui.entete("Les modèles", "Huit méthodes, une question chacune",
              "Du plus simple au plus élaboré : chaque méthode ajoute un ingrédient pour répondre à une question "
              "précise. Les chiffres viennent des trois périodes d'évaluation.")
    ui.en_une_phrase("on commence par recopier le passé, puis on apprend le calendrier, puis la température ; "
                     "un modèle plus compliqué ou une correction des erreurs n'apportent rien de plus.")

    lignes = []
    for m in vis.METHODES:
        valeurs = [scores_periode(p).loc[m, "MAE (MW)"] for p in vis.PERIODES]
        lignes.append(
            f'<tr{" class=vedette" if m == "M2" else ""}><td>{ui.pastille(m)}{ui.NOMS_LONGS[m]}</td>'
            + "".join(f'<td class="n">{ui.mw(v)}</td>' for v in valeurs) + "</tr>")
    st.markdown('<table class="propre"><tr><th>Méthode</th>' + "".join(f'<th class="n">{t}</th>' for t in vis.PERIODES.values())
                + "</tr>" + "".join(lignes) + "</table>", unsafe_allow_html=True)
    st.markdown('<p class="petit">Erreur moyenne par heure prévue, sur les jours communs à toutes les méthodes. '
                "La ligne surlignée est le modèle retenu.</p>", unsafe_allow_html=True)

    etiquettes = {"Benchmarks": "Benchmarks", "M1": "M1 · calendrier", "M2": "M2 · température  ★",
                  "M3": "M3 · boosting", "M4": "M4 · ARMA", "Plafond": "Plafond · météo parfaite"}
    onglets = st.tabs([etiquettes[nom] for nom in contenu.FICHES])
    for onglet, (cle, fiche) in zip(onglets, contenu.FICHES.items()):
        with onglet:
            st.markdown(f"### {fiche['titre']}")
            gauche, droite = st.columns([3, 2], gap="large")
            with gauche:
                st.markdown(
                    '<div class="fiche">'
                    f"<h4>L'idée</h4><p>{fiche['idee']}</p>"
                    "<h4>Ce qu'elle sait à 14 h la veille</h4><p>"
                    + "".join(f'<span class="puce-var">{v}</span>' for v in fiche["sait"]) + "</p>"
                    f"<h4>Comment elle apprend</h4><p>{fiche['apprend']}</p>"
                    f"<h4>Réglage choisi sur 2023</h4><p>{fiche['reglage']}</p>"
                    f'<h4>Code</h4><p><code>{fiche["fichier"]}</code></p></div>',
                    unsafe_allow_html=True,
                )
            with droite:
                for m in fiche["methodes"]:
                    ui.tuiles([(f"{ui.pastille(m)}{ui.NOMS_LONGS[m]} · {t}", ui.mw(scores_periode(p).loc[m, "MAE (MW)"]), "")
                               for p, t in vis.PERIODES.items()][:3] if len(fiche["methodes"]) == 1 else
                              [(f"{ui.pastille(m)}{ui.NOMS_LONGS[m]}", ui.mw(scores_periode("test").loc[m, "MAE (MW)"]),
                                "erreur moyenne 2024-2025")])
                st.markdown('<div class="fiche"><h4>Forces</h4><ul>' + "".join(f"<li>{x}</li>" for x in fiche["forces"])
                            + '</ul><h4>Limites</h4><ul>' + "".join(f"<li>{x}</li>" for x in fiche["faiblesses"])
                            + "</ul></div>", unsafe_allow_html=True)
            details_modele(cle)


def details_modele(cle):
    """Le petit complément chiffré de chaque fiche."""
    if cle == "M2":
        t = lire("ablation_m2_2023")
        t = t[t["variante_meteo"] == "M2-F"]
        noms = {"temp_38_ponderee": "38 stations, pondérées par la consommation des régions (retenue)",
                "temp_8_villes": "8 grandes villes", "temp_38_simple": "38 stations, moyenne simple"}
        st.markdown("**Les trois façons de calculer la température de la France, sur 2023**")
        st.markdown('<table class="propre"><tr><th>Température</th><th class="n">Erreur 2023</th></tr>' + "".join(
            f'<tr><td>{noms[r.candidat_temperature]}</td><td class="n">{ui.nombre(r.MAE_MW)} MW</td></tr>'
            for r in t.itertuples()) + "</table>", unsafe_allow_html=True)
        st.markdown('<p class="petit">Moins de 1 MW d\'écart : c\'est une égalité, écrite comme telle dans nos décisions.</p>',
                    unsafe_allow_html=True)
    elif cle == "M3":
        t = lire("selection_m3_validation_2023")
        st.markdown("**Les 4 réglages comparés sur 2023**")
        st.markdown('<table class="propre"><tr><th>Réglage</th><th class="n">Feuilles par arbre</th><th class="n">Étapes</th>'
                    '<th class="n">Pas</th><th class="n">Erreur 2023</th></tr>' + "".join(
                        f'<tr{" class=vedette" if i == 0 else ""}><td>{r.configuration}</td><td class="n">{r.max_leaf_nodes}</td>'
                        f'<td class="n">{r.max_iter}</td><td class="n">{ui.nombre(r.learning_rate, 2)}</td>'
                        f'<td class="n">{ui.mw(r.MAE_MW)}</td></tr>' for i, r in enumerate(t.itertuples())) + "</table>",
                    unsafe_allow_html=True)
    elif cle == "M4":
        d = lire("diagnostic_m4_2023")
        st.markdown("**Pourquoi M4 n'aide pas : les erreurs de M1 se répètent-elles d'un jour à l'autre ?**")
        st.markdown('<table class="propre"><tr><th>Erreurs de M1</th><th class="n">Ressemblance à 1 jour</th>'
                    '<th class="n">À 2 jours</th></tr>' + "".join(
                        f'<tr><td>{r.erreurs_de_M1}</td><td class="n">{ui.nombre(r.autocorrelation_1_jour, 2)}</td>'
                        f'<td class="n">{ui.nombre(r.autocorrelation_2_jours, 2)}</td></tr>' for r in d.itertuples())
                    + "</table>", unsafe_allow_html=True)
        st.markdown('<p class="petit">Une ressemblance de 1 voudrait dire « l\'erreur se répète exactement », 0 « aucun lien ». '
                    "À deux jours, plus aucun lien : rien à corriger pour l'après-midi.</p>", unsafe_allow_html=True)


# ===========================================================================
# 5. Explorer un jour
# ===========================================================================
def page_jour():
    ui.entete("Résultats", "Explorer un jour",
              "Choisissez une date : on compare ce qui s'est vraiment passé à ce que chaque méthode avait prévu "
              "la veille à 14 h.")
    rappel_periode()
    periode = periode_courante()
    p = previsions()
    p = p[p["periode"] == periode]
    erreurs = erreurs_jour_periode(periode)
    m2 = erreurs[erreurs["methode"] == "M2"].set_index("jour")
    dates = sorted(m2.index)

    c1, c2, c3 = st.columns([2, 2, 3])
    with c2:
        raccourci = st.radio("Raccourci", ["une date", "le pire jour de M2", "le meilleur jour de M2"], key="raccourci")
    defaut = {"le pire jour de M2": m2["mae"].idxmax(), "le meilleur jour de M2": m2["mae"].idxmin()}.get(
        raccourci, dates[len(dates) // 2])
    with c1:
        jour = pd.Timestamp(st.date_input("Jour à prévoir", value=defaut, min_value=dates[0], max_value=dates[-1],
                                          format="DD/MM/YYYY", disabled=raccourci != "une date"))
    with c3:
        methodes = st.pills("Méthodes affichées", vis.METHODES, selection_mode="multi",
                            default=["B0", "M2", "M3", "Plafond"], key="methodes_jour")
    if jour not in set(dates):
        st.warning("Ce jour n'est pas noté : jour de changement d'heure, ou hors de la période choisie.")
        return

    d = p[p["jour_cible"] == jour.strftime("%Y-%m-%d")].sort_values("heure")
    fig = go.Figure([ui.trace_methode(d["heure"], d["reel_MW"] / 1000, "reel_MW", hovertemplate="%{y:.1f} GW")])
    for m in methodes:
        fig.add_trace(ui.trace_methode(d["heure"], d[m] / 1000, m, hovertemplate="%{y:.1f} GW"))
    info = jours().loc[jour]
    veille = jours().loc[jour - pd.Timedelta(days=1)]
    ui.mise_en_forme(fig, f"{date_fr(jour).capitalize()} · {info['type_jour']}", hauteur=430, unite_y="GW",
                     titre_x="heure de la journée")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(dtick=2)
    ui.afficher(fig)

    e = erreurs[erreurs["jour"] == jour].set_index("methode")
    ecart = info["temperature_C"] - veille["temperature_C"]
    ui.tuiles([
        ("Température ce jour-là", f"{ui.nombre(info['temperature_C'])} °C", f"la veille : {ui.nombre(veille['temperature_C'])} °C, soit {'+' if ecart >= 0 else ''}{ui.nombre(ecart)} °C"),
        ("Erreur moyenne de M2", ui.mw(e.loc["M2", "mae"]), "M2 a prévu " + ("trop haut" if e.loc["M2", "biais"] > 0 else "trop bas")),
        ("Avec la vraie météo (plafond)", ui.mw(e.loc["Plafond", "mae"]), "ce que la météo exacte aurait permis"),
        ("Méthode simple (B0)", ui.mw(e.loc["B0", "mae"]), "recopier la consommation récente"),
    ])

    st.subheader("Le calendrier des erreurs de M2")
    st.markdown('<p class="petit">Chaque case est un jour, plus elle est foncée, plus M2 s\'est trompé. Survolez une case '
                "pour voir la date et l'erreur.</p>", unsafe_allow_html=True)
    calendrier_erreurs(m2["mae"])


def calendrier_erreurs(serie):
    """Un calendrier (semaines en colonnes, jours en lignes) coloré par l'erreur du jour."""
    s = serie.sort_index()
    debut = s.index.min() - pd.Timedelta(days=s.index.min().dayofweek)
    tous = pd.date_range(debut, s.index.max(), freq="D")
    valeurs = s.reindex(tous)
    semaines = ((tous - debut).days // 7).to_numpy()
    grille = np.full((7, semaines.max() + 1), np.nan)
    textes = np.full((7, semaines.max() + 1), "", dtype=object)
    for jour, semaine, v in zip(tous, semaines, valeurs.to_numpy()):
        grille[jour.dayofweek, semaine] = v
        textes[jour.dayofweek, semaine] = f"{date_fr(jour)}<br>" + ("non noté" if np.isnan(v) else f"erreur de M2 : {v:,.0f} MW".replace(",", " "))
    lundis = [debut + pd.Timedelta(weeks=int(k)) for k in range(semaines.max() + 1)]
    etiquettes = [(f"{MOIS[l.month - 1]} {l.year}" if l.month in (1, 7) else MOIS[l.month - 1])
                  if l.day <= 7 and l.month in (1, 4, 7, 10) else "" for l in lundis]
    fig = go.Figure(go.Heatmap(
        z=grille, x=list(range(len(lundis))), y=[j.capitalize()[:3] for j in JOURS_SEMAINE], text=textes,
        hovertemplate="%{text}<extra></extra>", xgap=2, ygap=2,
        colorscale=[[i / (len(ui.RAMPE_BLEUE) - 1), c] for i, c in enumerate(ui.RAMPE_BLEUE)],
        zmin=0, zmax=float(np.nanpercentile(s, 98)),
        colorbar=ui.echelle(),
    ))
    fig.update_xaxes(tickvals=[k for k, t in enumerate(etiquettes) if t], ticktext=[t for t in etiquettes if t],
                     showline=False, ticks="", tickangle=0)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.mise_en_forme(fig, hauteur=230, legende=False)
    fig.update_yaxes(showgrid=False)
    ui.afficher(fig)


# ===========================================================================
# 6. Classement
# ===========================================================================
def page_classement():
    ui.entete("Résultats", "Qui gagne ?",
              "Toutes les méthodes sont notées sur exactement les mêmes jours, avec plusieurs mesures. "
              "Puis on vérifie si les écarts sont réels ou dus au hasard.")
    ui.en_une_phrase("tous les modèles font au moins deux fois mieux que les méthodes simples ; M2 a la plus petite "
                     "erreur des modèles utilisables, à égalité statistique avec M3 mais plus simple.")
    rappel_periode()
    periode = periode_courante()
    s = scores_periode(periode)

    mae = s["MAE (MW)"].sort_values()
    fig = go.Figure(go.Bar(
        x=mae.values, y=[ui.NOMS_LONGS[m] for m in mae.index], orientation="h",
        marker=dict(color=[ui.COULEURS[m] for m in mae.index], line=dict(color=ui.SURFACE, width=2)),
        text=[ui.texte_barre(v) for v in mae.values], textposition="outside", textfont=dict(color=ui.ENCRE), cliponaxis=False,
        hovertemplate="%{y} : %{x:,.0f} MW<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    ui.mise_en_forme(fig, "Erreur moyenne par heure prévue", hauteur=360, titre_x="MW · plus c'est court, mieux c'est",
                     legende=False)
    fig.update_xaxes(range=[0, mae.max() * 1.18])
    ui.marge_etiquettes(fig, [ui.NOMS_LONGS[m] for m in mae.index])
    ui.afficher(fig)

    st.subheader("Toutes les mesures")
    colonnes = [("MAE (MW)", "Erreur moyenne", lambda v: ui.mw(v)), ("MAPE (%)", "En %", lambda v: ui.nombre(v) + " %"),
                ("RMSE (MW)", "RMSE", lambda v: ui.mw(v)), ("biais (MW)", "Biais", lambda v: ui.mw(v, signe=True)),
                ("erreur énergie du jour (GWh, absolue)", "Énergie du jour", lambda v: ui.nombre(v) + " GWh"),
                ("erreur pointe (MW, absolue)", "Pointe", lambda v: ui.mw(v)),
                ("heure de pointe exacte (% des jours)", "Heure de pointe exacte", lambda v: ui.nombre(v, 0) + " %")]
    st.markdown('<table class="propre"><tr><th>Méthode</th>' + "".join(f'<th class="n">{t}</th>' for _, t, _ in colonnes)
                + "</tr>" + "".join(
                    f'<tr{" class=vedette" if m == "M2" else ""}><td>{ui.pastille(m)}{ui.NOMS_LONGS[m]}</td>'
                    + "".join(f'<td class="n">{f(s.loc[m, c])}</td>' for c, _, f in colonnes) + "</tr>"
                    for m in vis.METHODES) + "</table>", unsafe_allow_html=True)
    st.markdown('<p class="petit">Biais positif : la méthode prévoit trop en moyenne. Énergie du jour : erreur sur le '
                "total consommé dans la journée. Heure de pointe exacte : part des jours où la méthode trouve l'heure "
                "du maximum.</p>", unsafe_allow_html=True)

    st.subheader("Les écarts sont-ils réels ?")
    nom = {"validation": "significativite_2023", "test": "significativite_2024_2025",
           "test_bonus": "test_bonus_2026_significativite"}[periode]
    t = lire(nom)
    t = t[t["perte"] == "MAE"]
    lignes = []
    for r in t.itertuples():
        m = vis.NOMS_COURTS[r.autre_methode]
        if r.conclusion == "écart non significatif":
            verdict = ui.badge("attention", "égalité")
            phrase = "l'écart peut venir du hasard"
        elif r.conclusion == "référence meilleure":
            verdict = ui.badge("bon", "M2 meilleur")
            phrase = "écart réel"
        else:
            verdict = ui.badge("probleme", f"{m} meilleur")
            phrase = "écart réel"
        lignes.append(f'<tr><td>M2 contre {ui.pastille(m)}{ui.NOMS_LONGS[m]}</td><td>{verdict}</td><td>{phrase}</td>'
                      f'<td class="n">{ui.nombre(100 * r.part_jours_reference_meilleure, 0)} %</td>'
                      f'<td class="n">{ui.nombre(r.p_valeur, 3)}</td></tr>')
    st.markdown('<table class="propre"><tr><th>Comparaison</th><th>Verdict</th><th></th><th class="n">Jours où M2 fait mieux</th>'
                '<th class="n">p-valeur</th></tr>' + "".join(lignes) + "</table>", unsafe_allow_html=True)
    st.markdown('<p class="petit">Test de Diebold-Mariano sur l\'erreur de chaque jour. Écart réel : moins de 5 % de chances '
                "qu'il soit dû au hasard (p-valeur inférieure à 0,05).</p>", unsafe_allow_html=True)

    st.subheader("Le classement tient-il d'une période à l'autre ?")
    fig = go.Figure()
    teintes = [ui.RAMPE_BLEUE[2], ui.RAMPE_BLEUE[4], ui.RAMPE_BLEUE[6]]
    ordre = ["B0", "M1", "M4", "M3", "M2", "Plafond"]
    for (cle, titre), teinte in zip(vis.PERIODES.items(), teintes):
        sp = scores_periode(cle)
        fig.add_trace(go.Bar(x=[ui.NOMS_LONGS[m] for m in ordre], y=[sp.loc[m, "MAE (MW)"] for m in ordre], name=titre,
                             marker=dict(color=teinte, line=dict(color=ui.SURFACE, width=2)),
                             hovertemplate=titre + " : %{y:,.0f} MW<extra></extra>"))
    ui.mise_en_forme(fig, hauteur=380, unite_y="erreur moyenne (MW)")
    fig.update_layout(barmode="group", bargap=0.25)
    ui.afficher(fig)
    st.markdown("Le même ordre se retrouve sur les trois périodes : les benchmarks loin derrière, puis M1 et M4, puis "
                "M3 et M2 au coude-à-coude. Seul M3 bouge : dernier des modèles en 2023, juste derrière M2 ensuite.")


# ===========================================================================
# 7. Quand ça rate
# ===========================================================================
def page_echecs():
    ui.entete("Résultats", "Quand ça rate, et pourquoi",
              "Une erreur moyenne cache des journées faciles et des journées très difficiles. "
              "Voici où se trouvent les erreurs, et ce qui les explique.")
    ui.en_une_phrase("les erreurs se concentrent en hiver, par grand froid, les jours fériés et l'après-midi ; les pires "
                     "journées sont des redoux soudains que le modèle ne pouvait pas voir venir.")
    rappel_periode()
    periode = periode_courante()
    erreurs = erreurs_jour_periode(periode).assign(
        classe=lambda d: pd.cut(d["temperature_C"], [-np.inf, 5, 10, 15, 20, np.inf],
                                labels=["< 5 °C", "5-10 °C", "10-15 °C", "15-20 °C", "> 20 °C"]),
        semaine=lambda d: d["jour"].dt.dayofweek.map(dict(enumerate(JOURS_SEMAINE))),
    )
    methodes = st.pills("Méthodes comparées", vis.METHODES, selection_mode="multi", default=["B0", "M1", "M2", "M3"],
                        key="methodes_echecs") or ["M2"]
    ui.legende_couleurs([m for m in vis.METHODES if m in methodes])

    def barres(critere, ordre, titre):
        t = erreurs[erreurs["methode"].isin(methodes)].groupby([critere, "methode"], observed=True)["mae"].mean().unstack()
        ordre = [o for o in ordre if o in t.index]
        nb = erreurs[erreurs["methode"] == "M2"].groupby(critere, observed=True).size()
        fig = go.Figure()
        for m in [x for x in vis.METHODES if x in methodes]:
            fig.add_trace(go.Bar(x=[f"{o[:3] if critere == 'semaine' else o}<br><span style='font-size:11px'>{nb.get(o, 0)} j</span>" for o in ordre],
                                 y=t.loc[ordre, m], name=ui.NOMS_LONGS[m],
                                 marker=dict(color=ui.COULEURS[m], line=dict(color=ui.SURFACE, width=2)),
                                 hovertemplate=ui.NOMS_LONGS[m] + " : %{y:,.0f} MW<extra></extra>"))
        ui.mise_en_forme(fig, titre, hauteur=320, unite_y="MW", legende=False)
        fig.update_layout(barmode="group", bargap=0.2)
        fig.update_xaxes(tickangle=0)
        ui.afficher(fig)

    c1, c2 = st.columns(2)
    with c1:
        barres("saison", ["hiver", "printemps", "été", "automne"], "Par saison")
        barres("type_jour", ["ouvré", "week-end", "pont", "férié", "Noël"], "Par type de jour")
    with c2:
        barres("classe", ["< 5 °C", "5-10 °C", "10-15 °C", "15-20 °C", "> 20 °C"], "Par température du jour")
        barres("semaine", JOURS_SEMAINE, "Par jour de la semaine")

    st.subheader("L'erreur de M2, heure par heure et mois par mois")
    p = previsions()
    p = p[p["periode"] == periode].assign(mois=lambda d: pd.to_datetime(d["jour_cible"]).dt.month,
                                           erreur=lambda d: (d["M2"] - d["reel_MW"]).abs())
    carte = p.pivot_table(index="heure", columns="mois", values="erreur", aggfunc="mean")
    fig = go.Figure(go.Heatmap(
        z=carte.values, x=[MOIS[m - 1] for m in carte.columns], y=[f"{h} h" for h in carte.index], xgap=2, ygap=1,
        colorscale=[[i / (len(ui.RAMPE_BLEUE) - 1), c] for i, c in enumerate(ui.RAMPE_BLEUE)],
        hovertemplate="%{x}, %{y} : %{z:,.0f} MW<extra></extra>",
        colorbar=ui.echelle()))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    ui.mise_en_forme(fig, hauteur=520, legende=False)
    fig.update_yaxes(showgrid=False)
    ui.afficher(fig)
    st.markdown("Deux choses sautent aux yeux : **l'hiver** (colonnes foncées à gauche et à droite) et **la coupure de "
                "13 h** (lignes plus foncées en dessous). À partir de 13 h, la consommation de la veille à la même heure "
                "n'est pas encore publiée à 14 h : le modèle doit se contenter de l'avant-veille.")

    st.subheader("Les 5 pires journées de M2, expliquées")
    m2 = erreurs[erreurs["methode"] == "M2"].set_index("jour")
    plafond = erreurs[erreurs["methode"] == "Plafond"].set_index("jour")["mae"]
    cartes = st.columns(5)
    for colonne, jour in zip(cartes, m2["mae"].nlargest(5).index):
        t, tv = jours().loc[jour, "temperature_C"], jours().loc[jour - pd.Timedelta(days=1), "temperature_C"]
        if plafond[jour] < 0.5 * m2.loc[jour, "mae"]:
            cause = (f"<b>Redoux soudain</b> : {ui.nombre(tv, 0)} °C la veille, {ui.nombre(t, 0)} °C ce jour. "
                     f"Avec la vraie météo : {ui.mw(plafond[jour])}.")
        elif m2.loc[jour, "type_jour"] in ("férié", "pont", "Noël"):
            cause = "<b>Jour spécial du calendrier</b>, que le modèle connaît mal."
        else:
            cause = "<b>Cause non identifiée</b> : ni la météo ni le calendrier ne l'expliquent."
        sens = "trop haut" if m2.loc[jour, "biais"] > 0 else "trop bas"
        with colonne:
            st.markdown(f'<div class="carte-jour"><div class="date">{date_fr(jour).capitalize()}</div>'
                        f'<div class="err" style="color:{ui.COULEURS["M2"]}">{ui.mw(m2.loc[jour, "mae"])}</div>'
                        f'<div class="petit">prévu {sens}</div><div class="cause">{cause}</div></div>',
                        unsafe_allow_html=True)
            d = previsions()
            d = d[(d["periode"] == periode) & (d["jour_cible"] == jour.strftime("%Y-%m-%d"))].sort_values("heure")
            fig = go.Figure([ui.trace_methode(d["heure"], d["reel_MW"] / 1000, "reel_MW", hovertemplate="%{y:.1f} GW"),
                             ui.trace_methode(d["heure"], d["M2"] / 1000, "M2", hovertemplate="%{y:.1f} GW"),
                             ui.trace_methode(d["heure"], d["Plafond"] / 1000, "Plafond", hovertemplate="%{y:.1f} GW")])
            ui.mise_en_forme(fig, hauteur=170, legende=False)
            fig.update_layout(margin=dict(l=4, r=4, t=6, b=4), hovermode="x unified")
            fig.update_xaxes(showticklabels=False, ticks="")
            fig.update_yaxes(tickfont=dict(size=10))
            ui.afficher(fig, cle=f"pire_{jour:%Y%m%d}")
    st.markdown(f'<p class="petit">Courbes : {ui.pastille("reel_MW")}réalité, {ui.pastille("M2")}M2, '
                f'{ui.pastille("Plafond")}plafond (vraie météo). Explication automatique : « redoux » si la vraie météo divise '
                "l'erreur au moins par deux.</p>", unsafe_allow_html=True)


# ===========================================================================
# 8. Le biais
# ===========================================================================
def page_biais():
    ui.entete("Résultats", "Un défaut commun : les modèles prévoyaient trop",
              "Le biais est l'erreur moyenne avec son signe. Il révèle un défaut que l'erreur moyenne seule cache.")
    ui.en_une_phrase("depuis 2023 la France consomme moins qu'avant à météo égale ; nos modèles, qui ont appris sur "
                     "2016-2022, prévoyaient un peu trop, puis ont rattrapé ce retard en 2026.")
    p = previsions().assign(mois=lambda d: d["jour_cible"].str[:7])
    biais = pd.DataFrame({m: (p[m] - p["reel_MW"]).groupby(p["mois"]).mean() for m in ["B0", "M2", "Plafond"]})
    fig = go.Figure()
    fig.add_trace(go.Bar(x=biais.index, y=biais["M2"], name=ui.NOMS_LONGS["M2"],
                         marker=dict(color=ui.COULEURS["M2"], line=dict(color=ui.SURFACE, width=1)),
                         hovertemplate="%{x} : %{y:+,.0f} MW<extra></extra>"))
    for m in ["Plafond", "B0"]:
        fig.add_trace(go.Scatter(x=biais.index, y=biais[m], name=ui.NOMS_LONGS[m], mode="lines+markers",
                                 line=dict(color=ui.COULEURS[m], width=2, dash=ui.TRAITS.get(m, "solid")),
                                 marker=dict(size=8, line=dict(color=ui.SURFACE, width=2)),
                                 hovertemplate="%{x} : %{y:+,.0f} MW<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=ui.ENCRE, width=1))
    ui.mise_en_forme(fig, "Biais moyen par mois", hauteur=420, unite_y="MW · au-dessus de 0 : on prévoit trop")
    fig.update_xaxes(type="category", tickangle=-45, nticks=14)
    ui.afficher(fig)
    ui.tuiles([(f"Biais de M2 · {titre}", ui.mw(scores_periode(cle).loc["M2", "biais (MW)"], signe=True), "")
               for cle, titre in vis.PERIODES.items()])
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Ce n'est pas la météo.** Le plafond, qui connaît la vraie météo, a le même défaut. La méthode "
                    "simple B0, qui recopie les jours récents, ne l'a pas : elle suit le niveau.")
    with c2, st.container(border=True):
        st.markdown("**Notre explication (une hypothèse).** La sobriété énergétique depuis la crise de 2022. Les modèles "
                    "réapprennent chaque mois avec les données récentes : le biais diminue. Nous ne l'avons pas corrigé, "
                    "car nous l'avons découvert sur le test : corriger après coup serait tricher.")


# ===========================================================================
# 9. Comment on a choisi
# ===========================================================================
def page_choix():
    ui.entete("Résultats", "Comment on a choisi",
              "Chaque ingrédient a été testé en le retirant ou en le remplaçant (une « ablation »), sur l'année 2023 "
              "seulement. Les années 2024 à 2026 n'ont servi qu'à juger.")
    ui.en_une_phrase("la consommation des jours précédents est l'ingrédient le plus important, la température vient "
                     "ensuite, et un modèle par heure fait bien mieux qu'un seul modèle.")

    def barres(t, nom, valeur, retenu, titre):
        couleurs = [ui.BLEU if r else ui.COULEURS["B2"] for r in t[retenu]]
        fig = go.Figure(go.Bar(x=t[valeur], y=t[nom], orientation="h", marker=dict(color=couleurs, line=dict(color=ui.SURFACE, width=2)),
                               text=[ui.texte_barre(v) for v in t[valeur]], textposition="outside", textfont=dict(color=ui.ENCRE),
                               cliponaxis=False, hovertemplate="%{y} : %{x:,.0f} MW<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        ui.mise_en_forme(fig, titre, hauteur=90 + 46 * len(t), titre_x="erreur moyenne en 2023 (MW) · en bleu, le choix retenu",
                         legende=False)
        fig.update_xaxes(range=[0, t[valeur].max() * 1.22])
        ui.marge_etiquettes(fig, t[nom])
        ui.afficher(fig)

    c1, c2 = st.columns(2)
    with c1:
        lags = lire("ablation_lags_m1_2023").assign(
            nom=lambda d: d["variante"].map({"LAG-A": "veille (matin) + semaine passée",
                                             "LAG-B": "veille (matin) + avant-veille + semaine passée",
                                             "LAG-C": "avant-veille + semaine passée", "LAG-D": "semaine passée seulement"}),
            retenu=lambda d: d["variante"] == "LAG-B")
        barres(lags, "nom", "MAE_MW", "retenu", "Quelles consommations passées ?")
        d14 = lire("decision14_un_modele_contre_24_2023").assign(retenu=lambda d: d["forme"].str.startswith("24"))
        barres(d14, "forme", "MAE_MW", "retenu", "Un modèle par heure, ou un seul ?")
    with c2:
        meteo = lire("ablation_m2_2023")
        v = meteo[meteo["candidat_temperature"] == "temp_38_ponderee"].assign(
            nom=lambda d: d["variante_meteo"].map({"M2-A": "température de 13 h seule", "M2-B": "+ température de la veille",
                                                   "M2-C": "+ température lissée", "M2-D": "13 h, lissée, degrés de chauffage",
                                                   "M2-E": "+ degrés de climatisation", "M2-F": "toutes (7 variables)"}),
            retenu=lambda d: d["variante_meteo"] == "M2-F")
        barres(v, "nom", "MAE_MW", "retenu", "Quelles informations de température ?")
        covid = lire("sensibilite_covid_2023").assign(
            nom=lambda d: d["modele"] + np.where(d["confinement_retire"], " sans le confinement", " avec le confinement"),
            retenu=lambda d: d["confinement_retire"])
        barres(covid, "nom", "MAE_MW", "retenu", "Faut-il enlever le confinement de 2020 ?")
    st.markdown(
        "- Sans la consommation de la veille et de l'avant-veille, **l'erreur double**.\n"
        "- La température seule fait **moins bien que rien** ; ce qui aide, ce sont les degrés de chauffage et une "
        "température lissée sur plusieurs jours (les bâtiments mettent du temps à refroidir).\n"
        "- Avec un seul modèle, l'effet du lundi serait le même à 4 h et à 19 h : **24 modèles** font nettement mieux.\n"
        "- Le confinement : nous avions décidé de l'enlever ; la vérification, faite trop tard, nous donne tort. "
        "Nous le disons, sans changer le modèle après coup."
    )


# ===========================================================================
# 10. Limites, reproduire, lexique
# ===========================================================================
def page_limites():
    ui.entete("Pour aller plus loin", "Limites, et ce qu'on améliorerait",
              "Un bon modèle, c'est aussi savoir quand ne pas lui faire confiance.")
    ui.en_une_phrase("le modèle est fiable la plupart du temps ; il faut s'en méfier lors des changements brusques de "
                     "température, des jours spéciaux et des changements de niveau de consommation.")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("#### Quand s'en méfier")
        st.markdown("- **Changements brusques de température** : pas de prévision météo, seulement l'observation de 13 h.\n"
                    "- **Fins d'année et jours fériés**, surtout un férié qui tombe un week-end.\n"
                    "- **Changement de niveau de consommation**, comme après la crise de l'énergie.")
    with c2, st.container(border=True):
        st.markdown("#### Ce que nous disons honnêtement")
        st.markdown("- Le test 2024-2025 de M2 a été lancé **avant** que M3 et M4 soient construits.\n"
                    "- M4 utilisait une heure pas encore publiée : **erreur trouvée, corrigée**, test relancé.\n"
                    "- Les données RTE sont les versions définitives : nos erreurs sont sans doute **un peu optimistes**.\n"
                    "- Le test 2026 ne couvre que **six mois**, surtout l'hiver et le printemps.")
    test = scores_periode("test")
    st.subheader("Ce qui améliorerait le plus la prévision")
    ui.tuiles([
        ("1 · Une prévision météo du lendemain", f"−{ui.mw(test.loc['M2', 'MAE (MW)'] - test.loc['Plafond', 'MAE (MW)'])}",
         "d'erreur moyenne, d'après le plafond « météo parfaite »"),
        ("2 · Suivre le niveau récent", "biais ↓", "une tendance, ou plus de poids aux années récentes"),
        ("3 · Traiter les jours spéciaux", "fériés", "veille de Noël, fériés qui tombent un week-end"),
    ])


def page_reproduire():
    ui.entete("Pour aller plus loin", "Reproduire le projet",
              "Tout le projet se refait avec une suite de commandes, depuis un dossier vide. "
              "Les résultats sont identiques à chaque fois.")
    ui.en_une_phrase("douze commandes, dans l'ordre, et plus de 500 tests automatiques pour vérifier qu'aucune "
                     "information du futur n'est utilisée.")
    etapes = [
        ("pip install -r requirements.txt", "installer les bibliothèques, versions figées"),
        ("python -m src.rte", "consommation RTE"), ("python -m src.pipeline_meteo", "météo : 40 stations, trous et anomalies"),
        ("python -m src.calendrier", "jours fériés, ponts, vacances"), ("python -m src.features", "variables connues à 14 h"),
        ("python -m src.experiences", "choix sur 2023 : ablations, réglages"),
        ("python -m src.experiences --test-final", "test 2024-2025 des réglages gelés"),
        ("python -m src.analyses --test-final", "plafond, erreurs par groupe, significativité"),
        ("python -m src.comparaison --test-final", "toutes les méthodes sur les mêmes jours"),
        ("python -m src.test_bonus", "test bonus 2026, données préparées à part"),
        ("python -m src.visualisation", "fichiers de ce tableau de bord"),
        ("pytest", "tous les tests"),
    ]
    st.markdown('<table class="propre"><tr><th>#</th><th>Commande</th><th>Ce qu\'elle fait</th></tr>' + "".join(
        f"<tr><td>{i}</td><td><code>{c}</code></td><td>{q}</td></tr>" for i, (c, q) in enumerate(etapes, start=1))
        + "</table>", unsafe_allow_html=True)
    st.markdown('<p class="petit">Le détail (durées, fichiers produits) est dans le README du dépôt. Les décisions et leur '
                "historique sont dans <code>docs/decisions.md</code>.</p>", unsafe_allow_html=True)


def page_lexique():
    ui.entete("Pour aller plus loin", "Lexique", "Les mots techniques du projet, expliqués simplement.")
    st.markdown('<table class="propre">' + "".join(
        f'<tr><td style="width:28%"><b>{mot}</b></td><td>{definition}</td></tr>' for mot, definition in contenu.LEXIQUE)
        + "</table>", unsafe_allow_html=True)


# ===========================================================================
# Navigation
# ===========================================================================
def main():
    st.set_page_config(page_title="Prévision de la consommation électrique", page_icon="⚡", layout="wide")
    ui.appliquer_style()
    if not (RESULTATS / "visualisation_previsions.csv").exists():
        st.error("Fichiers absents : lancer d'abord `python -m src.visualisation` (voir le README).")
        st.stop()
    definitions = {
        "Comprendre": [("accueil", page_accueil, "Le projet en bref", ":material/bolt:"),
                       ("methode", page_methode, "La méthode", ":material/schedule:"),
                       ("donnees", page_donnees, "Les données", ":material/monitoring:")],
        "Les modèles": [("modeles", page_modeles, "Les huit méthodes", ":material/model_training:")],
        "Résultats": [("jour", page_jour, "Explorer un jour", ":material/calendar_month:"),
                      ("classement", page_classement, "Qui gagne ?", ":material/leaderboard:"),
                      ("echecs", page_echecs, "Quand ça rate", ":material/troubleshoot:"),
                      ("biais", page_biais, "Un défaut commun", ":material/balance:"),
                      ("choix", page_choix, "Comment on a choisi", ":material/science:")],
        "Pour aller plus loin": [("limites", page_limites, "Limites", ":material/warning:"),
                                 ("reproduire", page_reproduire, "Reproduire", ":material/terminal:"),
                                 ("lexique", page_lexique, "Lexique", ":material/menu_book:")],
    }
    sections = {}
    for section, pages in definitions.items():
        sections[section] = []
        for cle, fonction, titre, icone in pages:
            options = {"default": True} if cle == "accueil" else {"url_path": cle}
            PAGES[cle] = st.Page(fonction, title=titre, icon=icone, **options)
            sections[section].append(PAGES[cle])
    with st.sidebar:
        st.markdown('<div class="titre-app">⚡ Prévision J+1</div><div class="sous-app">Consommation électrique de la '
                    "France, prévue chaque jour à 14 h</div>", unsafe_allow_html=True)
    page = st.navigation(sections)
    with st.sidebar:
        st.caption("Martine Ouedraogo · Khadim NGOM  \nMaster 1 Data Science, Université Lyon 2")
    page.run()


if __name__ == "__main__":
    main()
