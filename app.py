"""Página de inicio — Mapa de Probabilidad de Sobrevivientes (Caracas y La Guaira)."""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.pipeline import build_zone
from core.sources import fmt_vet_utc, parse_iso
from core.ui import ALERT_COLORS, apply_chrome, render_sources

st.set_page_config(page_title="Probabilidad de Sobrevivientes", page_icon="🛰️", layout="wide")

config = load_config()
lang = apply_chrome(config)

ZONA_PAGES = [
    ("pages/1_Caracas_Libertador.py",       "🔴 Libertador"),
    ("pages/2_Caracas_Sucre_Petare.py",     "🔴 Sucre / Petare"),
    ("pages/3_Caracas_Baruta_ElHatillo.py", "🔴 Baruta / Hatillo"),
    ("pages/4_La_Guaira_Litoral.py",        "🔴 La Guaira"),
]

V1 = 72
V2 = 120


@st.cache_data(ttl=110, show_spinner=True)
def _resumen(_salt: int):
    rows, ctx = [], None
    for z in config["zonas"]:
        df, ctx = build_zone(z, config, with_osm=False)
        rows.append({"nombre": z["nombre"],
                     "alta": int((df["prioridad"] == "alta").sum()),
                     "mmi": float(df["mmi"].max()) if ctx["shakemap_ok"] else float("nan")})
    return pd.DataFrame(rows), ctx


resumen, ctx = _resumen(config.get("autorefresco_segundos", 0))
render_sources(ctx, lang)

# Sidebar: navegación
st.sidebar.markdown("---")
st.sidebar.markdown("**🗺️ Ir a zona**")
for path, label in ZONA_PAGES:
    st.sidebar.page_link(path, label=label)

# ── TÍTULO compacto ──────────────────────────────────────────────────────────
st.title("🛰️ " + t("app_title", lang))
st.caption(t("app_subtitle", lang))

# ── ZONA DE MAPAS — elemento principal, arriba de todo ───────────────────────
lbl_cta = ("Selecciona una zona para abrir el mapa en tiempo real:"
           if lang == "es" else "Select a zone to open the live map:")
st.markdown(f"### {lbl_cta}")

zona_rows = resumen.to_dict("records")
col_alta  = t("col_celdas_alta", lang)
pairs = list(zip(zona_rows, ZONA_PAGES))

for i in range(0, len(pairs), 2):
    cols = st.columns(2, gap="medium")
    for j, col in enumerate(cols):
        if i + j >= len(pairs):
            break
        row, (path, _) = pairs[i + j]
        alta    = int(row["alta"])
        mmi_val = f"{row['mmi']:.1f}" if not pd.isna(row["mmi"]) else "—"

        if alta > 200:
            border, bg, badge = "#b71c1c", "rgba(183,28,28,0.07)", "🔴"
        elif alta > 50:
            border, bg, badge = "#e65100", "rgba(230,81,0,0.07)", "🟠"
        else:
            border, bg, badge = "#1565c0", "rgba(21,101,192,0.06)", "🔵"

        with col:
            st.markdown(f"""
<div style="border:2px solid {border};border-radius:12px;padding:14px 16px 10px;
  background:{bg};margin-bottom:4px;">
  <div style="font-size:1.05rem;font-weight:700;color:{border};margin-bottom:6px;">
    {badge} {row['nombre']}
  </div>
  <div style="font-size:0.85rem;color:#444;margin-bottom:2px;">
    ⚠️ <b>{alta}</b> {col_alta.lower()}
  </div>
  <div style="font-size:0.82rem;color:#666;">
    📳 MMI máx: <b>{mmi_val}</b>
  </div>
</div>""", unsafe_allow_html=True)
            st.page_link(path,
                         label="📍 Abrir mapa en tiempo real →" if lang == "es"
                               else "📍 Open live map →")

st.markdown("---")

# ── MODO + INTRO ─────────────────────────────────────────────────────────────
if ctx["modo"] == "operativo":
    st.success(t("modo_operativo_label", lang))
else:
    st.warning(t("modo_demo_label", lang))

with st.expander("ℹ️ " + ("¿Qué hace esta herramienta?" if lang == "es"
                           else "What does this tool do?"), expanded=False):
    st.markdown(t("intro", lang))

# ── SECUENCIA SÍSMICA (compacta) ─────────────────────────────────────────────
s = ctx["sismo"]
adicionales = ctx.get("sismos_adicionales", [])
with st.expander("📍 " + t("sismo_titulo", lang), expanded=False):
    if adicionales:
        a = adicionales[0]
        st.warning(t("sismo_doble_banner", lang,
                     m1=s.get("id", "us6000t7zp"), mag1=s.get("magnitud", 7.5),
                     m2=a.get("id", "us6000t7zc"), mag2=a.get("magnitud", 7.2)))
    c = st.columns(4)
    c[0].metric(t("magnitud", lang), f"M{s.get('magnitud')}")
    c[1].metric(t("profundidad", lang), f"{s.get('profundidad_km','?')} km")
    c[2].metric(t("epicentro", lang), f"{s['epicentro']['lat']:.3f}, {s['epicentro']['lon']:.3f}")
    if ctx.get("alert_pager"):
        c[3].metric(t("pager_nivel", lang),
                    f"{ALERT_COLORS.get(ctx['alert_pager'],'')} {ctx['alert_pager'].upper()}")
    st.caption(f"📌 {s.get('lugar','')} · 🕒 {t('hora_evento', lang)}: "
               f"{fmt_vet_utc(parse_iso(s['origen_iso']))}")
    if s.get("url"):
        st.caption(f"🔗 [{t('evento_real', lang)}]({s['url']})")
        if adicionales and adicionales[0].get("url"):
            st.caption(f"🔗 [{t('sismo_secundario', lang)} M{adicionales[0].get('magnitud')}]"
                       f"({adicionales[0]['url']})")
    st.caption(t("actualizacion_tiempo_real", lang))

# ── VENTANAS ESTADÍSTICAS (plegadas) ─────────────────────────────────────────
hs = ctx["hours_since"]
if hs < V1:
    fase, fase_color = ("ventana_principal" if lang == "es" else "primary_window"), "info"
elif hs < V2:
    fase, fase_color = ("ventana_secundaria" if lang == "es" else "secondary_window"), "warning"
else:
    fase, fase_color = ("fase_extendida" if lang == "es" else "extended_phase"), "warning"

FASES = {
    "es": {
        "ventana_principal":  ("🟢 Ventana principal (0–72 h)",
                               "Mayor probabilidad estadística. Priorizar celdas de alta prioridad de inmediato."),
        "ventana_secundaria": ("🟡 Ventana secundaria (72–120 h)",
                               "Probabilidad reducida pero documentada. INSARAG activo. Turquía 2023: +100 h."),
        "fase_extendida":     ("🔵 Fase extendida (+120 h)",
                               "Haití 2010 (+15 días), Armenia 1988 (+8 días), México 1985 (+14 días)."),
    },
    "en": {
        "primary_window":   ("🟢 Primary window (0–72 h)",
                             "Highest statistical probability. Prioritize high-priority cells now."),
        "secondary_window": ("🟡 Secondary window (72–120 h)",
                             "Reduced but documented. INSARAG active. Turkey 2023: +100 h."),
        "extended_phase":   ("🔵 Extended phase (+120 h)",
                             "Haiti 2010 (+15 days), Armenia 1988 (+8 days), Mexico 1985 (+14 days)."),
    },
}

fase_titulo, fase_texto = FASES.get(lang, FASES["es"]).get(fase, ("", ""))
expander_label = f"⏳ {t('reloj_titulo', lang)} — {hs:.0f} h"
with st.expander(expander_label, expanded=False):
    getattr(st, fase_color)(f"**{fase_titulo}**  \n{fase_texto}")
    col1, col2, col3 = st.columns(3)
    col1.metric(t("horas_transcurridas", lang), f"{hs:.1f} h")
    col2.metric("Ventana 72 h" if lang == "es" else "72-h window",
                f"{max(V1-hs,0):.1f} h" if hs < V1 else "✓")
    col3.metric("Ventana 120 h" if lang == "es" else "120-h window",
                f"{max(V2-hs,0):.1f} h" if hs < V2 else "✓")
    st.progress(min(hs/V1, 1.0))
    st.caption("INSARAG · Coburn & Spence (2002)")
    st.progress(min(hs/V2, 1.0))
    if ctx.get("proyec_ok"):
        st.caption(t("nota_proyeccion", lang))

# ── PELIGROS SECUNDARIOS ──────────────────────────────────────────────────────
gf = ctx.get("ground_failure") or {}
if gf:
    with st.expander("⚠️ " + t("gf_titulo", lang), expanded=False):
        g = st.columns(2)
        if gf.get("liquefaction_pop"):
            g[0].metric(f"{ALERT_COLORS.get(gf.get('liquefaction_alert'),'')} "
                        f"{t('exposicion_licuefaccion', lang)}",
                        f"{int(gf['liquefaction_pop']):,}")
        if gf.get("landslide_pop"):
            g[1].metric(f"{ALERT_COLORS.get(gf.get('landslide_alert'),'')} "
                        f"{t('exposicion_deslizamiento', lang)}",
                        f"{int(gf['landslide_pop']):,}")
        st.caption(f"🔗 [{config['fuentes']['usgs_ground_failure']['nombre']}]"
                   f"({config['fuentes']['usgs_ground_failure']['url']})")

st.caption(f"🕒 {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")
