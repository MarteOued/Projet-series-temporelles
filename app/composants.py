"""Briques communes du tableau de bord : style, couleurs, cartes, mise en forme des graphiques.

Les couleurs des méthodes sont FIXES : une méthode garde la même couleur sur toutes
les pages, quel que soit le nombre de méthodes affichées. Palette validée pour les
daltoniens (script de validation de la palette, mode clair) : M2, M3, Plafond, M1,
M4 dans cet ordre ; les benchmarks sont en gris avec des pointillés.
"""

import html
import re

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Couleurs
# ---------------------------------------------------------------------------
ENCRE = "#0b0b0b"
ENCRE_2 = "#52514e"
DISCRET = "#898781"
GRILLE = "#e1e0d9"
AXE = "#c3c2b7"
SURFACE = "#fcfcfb"
PLAN = "#f9f9f7"
BLEU = "#2a78d6"

COULEURS = {
    "reel_MW": ENCRE,
    "M2": "#2a78d6", "M3": "#eb6834", "Plafond": "#1baf7a", "M1": "#eda100", "M4": "#e87ba4",
    "B0": "#6f6e69", "B1": "#9a9890", "B2": "#bab9b0",
}
TRAITS = {"B0": "dot", "B1": "dash", "B2": "dashdot", "Plafond": "dash"}
ETATS = {"bon": "#0ca30c", "attention": "#fab219", "probleme": "#d03b3b"}
# Rampe séquentielle (une seule teinte, du clair au foncé) pour les cartes de chaleur
RAMPE_BLEUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

NOMS_LONGS = {
    "B0": "B0 · Veille effective", "B1": "B1 · Semaine précédente", "B2": "B2 · Moyenne de 4 semaines",
    "M1": "M1 · Calendrier + passé", "M2": "M2 · M1 + température", "M3": "M3 · Gradient boosting",
    "M4": "M4 · M1 + correction ARMA", "Plafond": "Plafond · Météo parfaite",
}


# ---------------------------------------------------------------------------
# Style de la page
# ---------------------------------------------------------------------------
CSS = f"""
<style>
:root {{
  --encre: {ENCRE}; --encre-2: {ENCRE_2}; --discret: {DISCRET}; --grille: {GRILLE};
  --surface: {SURFACE}; --plan: {PLAN}; --bleu: {BLEU}; --anneau: rgba(11,11,11,0.10);
}}
.block-container {{ max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }}
h1, h2, h3 {{ letter-spacing: -0.01em; text-wrap: balance; }}
h2 {{ margin-top: 0.6rem !important; }}
.entete {{ padding: 0.2rem 0 1.1rem; border-bottom: 1px solid var(--grille); margin-bottom: 1.3rem; }}
.entete .surtitre {{ font-size: 0.78rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--bleu); }}
.entete h1 {{ font-size: 2.35rem; font-weight: 800; line-height: 1.12; margin: 0.25rem 0 0.55rem; padding: 0; color: var(--encre); }}
.entete p {{ font-size: 1.12rem; color: var(--encre-2); max-width: 72ch; margin: 0; line-height: 1.55; }}
.phrase {{ background: var(--surface); border: 1px solid var(--anneau); border-left: 4px solid var(--bleu);
  border-radius: 10px; padding: 0.85rem 1.1rem; font-size: 1.05rem; line-height: 1.55; margin: 0.2rem 0 1.4rem; color: var(--encre); }}
.phrase b {{ color: var(--bleu); }}
.tuiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 0.9rem; margin: 0.4rem 0 1.2rem; }}
.tuile {{ background: var(--surface); border: 1px solid var(--anneau); border-radius: 12px; padding: 1rem 1.1rem; }}
.tuile .libelle {{ font-size: 0.85rem; color: var(--encre-2); line-height: 1.35; }}
.tuile .valeur {{ font-size: 1.9rem; font-weight: 700; color: var(--encre); line-height: 1.15; margin-top: 0.25rem; }}
.tuile .detail {{ font-size: 0.84rem; color: var(--discret); margin-top: 0.3rem; line-height: 1.4; }}
.heros {{ background: var(--surface); border: 1px solid var(--anneau); border-radius: 16px; padding: 1.6rem 1.8rem; margin: 0.3rem 0 1.2rem;
  display: grid; grid-template-columns: minmax(220px, 0.9fr) 2fr; gap: 1.6rem; align-items: center; }}
.heros .chiffre {{ font-size: 4.2rem; font-weight: 800; color: var(--bleu); line-height: 1; }}
.heros .sous {{ font-size: 0.95rem; color: var(--encre-2); margin-top: 0.5rem; }}
.heros .texte {{ font-size: 1.08rem; line-height: 1.6; color: var(--encre); }}
@media (max-width: 760px) {{ .heros {{ grid-template-columns: 1fr; }} .entete h1 {{ font-size: 1.8rem; }} }}
.pastille {{ display: inline-block; width: 0.72rem; height: 0.72rem; border-radius: 50%; vertical-align: -0.05rem; margin-right: 0.35rem; }}
.badge {{ display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.82rem; font-weight: 600; padding: 0.1rem 0.6rem;
  border-radius: 999px; border: 1px solid currentColor; white-space: nowrap; }}
.puce-var {{ display: inline-block; font-size: 0.82rem; padding: 0.12rem 0.55rem; margin: 0 0.3rem 0.35rem 0; border-radius: 6px;
  background: var(--plan); border: 1px solid var(--grille); color: var(--encre); }}
.fiche h4 {{ font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--discret); margin: 0.9rem 0 0.35rem; }}
.fiche p, .fiche li {{ font-size: 1rem; line-height: 1.55; }}
.flux {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.6rem; margin: 0.5rem 0 1rem; }}
@media (max-width: 1100px) {{ .flux {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .flux {{ grid-template-columns: 1fr; }} }}
.etape::after {{ content: "→"; position: absolute; right: -0.55rem; top: 42%; color: var(--discret); font-weight: 700; }}
.etape:last-child::after {{ content: ""; }}
.etape {{ background: var(--surface); border: 1px solid var(--anneau); border-radius: 12px; padding: 0.8rem 0.9rem; position: relative; }}
.etape .num {{ font-size: 0.75rem; font-weight: 700; color: var(--bleu); letter-spacing: 0.06em; }}
.etape .nom {{ font-weight: 700; font-size: 1rem; margin: 0.15rem 0 0.25rem; color: var(--encre); }}
.etape .quoi {{ font-size: 0.86rem; color: var(--encre-2); line-height: 1.4; }}
.etape code {{ font-size: 0.78rem; }}
.horloge {{ display: grid; grid-template-columns: repeat(48, 1fr); gap: 2px; margin: 0.6rem 0 0.4rem; }}
.horloge div {{ height: 34px; border-radius: 3px; }}
.legende-horloge {{ display: flex; flex-wrap: wrap; gap: 0.4rem 1.4rem; font-size: 0.9rem; color: var(--encre-2); margin-bottom: 1rem; }}
.legende {{ display: flex; flex-wrap: wrap; gap: 0.3rem 1.2rem; font-size: 0.92rem; color: var(--encre); margin: 0.2rem 0 0.6rem; }}
.legende .trait {{ display: inline-block; width: 1.3rem; height: 0; border-top-width: 3px; vertical-align: middle; margin-right: 0.4rem; }}
.choix-periode {{ font-size: 0.85rem; color: var(--encre-2); margin-bottom: -0.4rem; }}
.carte-jour {{ background: var(--surface); border: 1px solid var(--anneau); border-radius: 12px; padding: 0.9rem 1rem; min-height: 15.5rem; }}
.carte-jour .date {{ font-weight: 700; font-size: 1.05rem; }}
.carte-jour .err {{ font-size: 1.5rem; font-weight: 700; margin: 0.2rem 0; }}
.carte-jour .cause {{ font-size: 0.9rem; color: var(--encre-2); line-height: 1.45; }}
.petit {{ font-size: 0.86rem; color: var(--discret); line-height: 1.45; }}
[data-testid="stSidebar"] .titre-app {{ font-weight: 800; font-size: 1.15rem; line-height: 1.25; color: var(--encre); }}
[data-testid="stSidebar"] .sous-app {{ font-size: 0.85rem; color: var(--encre-2); margin-bottom: 0.4rem; }}
table.propre {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
table.propre th {{ text-align: left; font-size: 0.8rem; color: var(--discret); font-weight: 700; border-bottom: 1px solid var(--axe, #c3c2b7); padding: 0.45rem 0.6rem; }}
table.propre td {{ border-bottom: 1px solid var(--grille); padding: 0.5rem 0.6rem; vertical-align: top; }}
table.propre td.n, table.propre th.n {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
table.propre tr.vedette td {{ font-weight: 700; background: rgba(42,120,214,0.06); }}
</style>
"""


def appliquer_style():
    st.markdown(CSS, unsafe_allow_html=True)


def echapper(texte):
    return html.escape(str(texte))


def entete(surtitre, titre, chapeau):
    st.markdown(
        f'<div class="entete"><div class="surtitre">{surtitre}</div><h1>{titre}</h1><p>{chapeau}</p></div>',
        unsafe_allow_html=True,
    )


def en_une_phrase(texte):
    st.markdown(f'<div class="phrase"><b>En une phrase.</b> {texte}</div>', unsafe_allow_html=True)


def tuiles(elements):
    """elements : liste de (libellé, valeur, détail)."""
    contenu = "".join(
        f'<div class="tuile"><div class="libelle">{libelle}</div><div class="valeur">{valeur}</div>'
        f'<div class="detail">{detail}</div></div>'
        for libelle, valeur, detail in elements
    )
    st.markdown(f'<div class="tuiles">{contenu}</div>', unsafe_allow_html=True)


def pastille(methode):
    return f'<span class="pastille" style="background:{COULEURS[methode]}"></span>'


def badge(etat, texte):
    icone = {"bon": "✓", "attention": "=", "probleme": "!"}[etat]
    return f'<span class="badge" style="color:{ETATS[etat]}">{icone} {texte}</span>'


def mw(valeur, signe=False):
    texte = f"{valeur:+,.0f}" if signe else f"{valeur:,.0f}"
    return texte.replace(",", " ") + " MW"


def nombre(valeur, decimales=1):
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------------------
# Graphiques : une seule mise en forme pour tout le tableau de bord
# ---------------------------------------------------------------------------
CONFIG_GRAPHIQUE = {"displayModeBar": False, "responsive": True}


def mise_en_forme(fig, titre=None, hauteur=380, unite_y=None, titre_x=None, legende=True):
    fig.update_layout(
        title=dict(text=titre, font=dict(size=16, color=ENCRE), x=0, xanchor="left") if titre else None,
        height=hauteur,
        margin=dict(l=8, r=12, t=48 if titre else 12, b=8),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Source Sans 3, Source Sans Pro, sans-serif", size=13, color=ENCRE_2),
        separators=", ",
        showlegend=legende,
        legend=dict(orientation="h", yanchor="top", y=-0.16, xanchor="left", x=0, font=dict(size=12, color=ENCRE),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="white", bordercolor=GRILLE, font=dict(color=ENCRE, size=13)),
        barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXE, ticks="outside", tickcolor=AXE, tickfont=dict(color=DISCRET), automargin=True,
                     title=dict(text=titre_x, font=dict(color=ENCRE_2)) if titre_x else None, zeroline=False)
    fig.update_yaxes(gridcolor=GRILLE, gridwidth=1, linecolor=AXE, tickfont=dict(color=DISCRET), zeroline=False, automargin=True,
                     title=dict(text=unite_y, font=dict(color=ENCRE_2)) if unite_y else None)
    return fig


def legende(methodes, reel=True):
    """Une légende commune, au-dessus d'une grille de petits graphiques."""
    styles = {"dot": "dotted", "dash": "dashed", "dashdot": "dashed"}
    elements = ([("Réalité", ENCRE, "solid")] if reel else []) + [
        (NOMS_LONGS[m], COULEURS[m], styles.get(TRAITS.get(m, "solid"), "solid")) for m in methodes]
    st.markdown('<div class="legende">' + "".join(
        f'<span><span class="trait" style="border-top-style:{trait};border-top-color:{couleur}"></span>{nom}</span>'
        for nom, couleur, trait in elements) + "</div>", unsafe_allow_html=True)


def legende_couleurs(methodes):
    """Légende par carrés de couleur (pour les barres)."""
    st.markdown('<div class="legende">' + "".join(f"<span>{pastille(m)}{NOMS_LONGS[m]}</span>" for m in methodes)
                + "</div>", unsafe_allow_html=True)


def texte_barre(valeur):
    """Valeur écrite au bout d'une barre, avec un petit espace pour ne pas la toucher."""
    return "\u2002" + mw(valeur)


def echelle(titre="MW"):
    return dict(title=dict(text=titre, side="top"), thickness=10, outlinewidth=0, tickfont=dict(color=DISCRET), len=0.9)


def marge_etiquettes(fig, etiquettes, taille=13):
    """Réserve à gauche la place des étiquettes d'un graphique à barres horizontales (pour qu'aucune ne soit coupée)."""
    lignes = [max(re.sub(r"<[^>]+>", "|", str(e)).split("|"), key=len) for e in etiquettes]
    largeur = max(len(x) for x in lignes) * taille * 0.56 + 18
    fig.update_layout(margin=dict(l=int(largeur)))
    fig.update_yaxes(automargin=False)
    return fig


def afficher(fig, cle=None):
    st.plotly_chart(fig, config=CONFIG_GRAPHIQUE, key=cle)


def trace_methode(x, y, methode, **options):
    """Une courbe de méthode avec sa couleur et son trait fixes."""
    epaisseur = 3.5 if methode == "reel_MW" else 2
    return go.Scatter(
        x=x, y=y, mode="lines", name="Réalité" if methode == "reel_MW" else NOMS_LONGS[methode],
        line=dict(color=COULEURS[methode], width=epaisseur, dash=TRAITS.get(methode, "solid")), **options,
    )
