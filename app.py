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

# Ventanas estadísticas (fuente: INSARAG Guidelines 2020; Coburn & Spence 2002)
V1 = 72    # ventana principal
V2 = 120   # ventana secundaria (5 días)


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

# Navegación sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("**🗺️ Ir a zona**")
for path, label in ZONA_PAGES:
    st.sidebar.page_link(path, label=label)

st.title("🛰️ " + t("app_title", lang))
st.caption(t("app_subtitle", lang))
(st.error if ctx["modo"] == "operativo" else st.warning)(
    t("modo_operativo_label" if ctx["modo"] == "operativo" else "modo_demo_label", lang))
st.markdown(t("intro", lang))

# --- Secuencia sísmica ---
s = ctx["sismo"]
st.subheader("📍 " + t("sismo_titulo", lang))
adicionales = ctx.get("sismos_adicionales", [])
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
st.caption(f"📌 {s.get('lugar','')} · 🕒 {t('hora_evento', lang)}: {fmt_vet_utc(parse_iso(s['origen_iso']))}")
if s.get("url"):
    st.caption(f"🔗 [{t('evento_real', lang)}]({s['url']})")
    if adicionales and adicionales[0].get("url"):
        st.caption(f"🔗 [{t('sismo_secundario', lang)} M{adicionales[0].get('magnitud')}]({adicionales[0]['url']})")
st.caption(t("actualizacion_tiempo_real", lang))

# --- Ventanas estadísticas de rescate ---
st.subheader("⏳ " + t("reloj_titulo", lang))
hs = ctx["hours_since"]

# Fase actual
if hs < V1:
    fase, fase_color = ("ventana_principal" if lang == "es" else "primary_window"), "info"
elif hs < V2:
    fase, fase_color = ("ventana_secundaria" if lang == "es" else "secondary_window"), "warning"
else:
    fase, fase_color = ("fase_extendida" if lang == "es" else "extended_phase"), "warning"

FASES = {
    "es": {
        "ventana_principal":  ("🟢 Ventana principal (0–72 h)",
                               "Mayor probabilidad estadística de rescate con vida. Priorizar inmediatamente celdas de alta prioridad."),
        "ventana_secundaria": ("🟡 Ventana secundaria (72–120 h)",
                               "Probabilidad reducida pero **documentada**. Con acceso a aire y agua, la supervivencia se extiende. "
                               "INSARAG mantiene operaciones activas. Turquía 2023: rescates a +100 h. Continuar con foco en "
                               "reportes confirmados y espacios confinados (sótanos, cajas de escalera)."),
        "fase_extendida":     ("🔵 Fase extendida (+120 h)",
                               "Casos excepcionales documentados: Haití 2010 (+15 días), Armenia 1988 (+8 días), México 1985 (+14 días). "
                               "La probabilidad es baja pero real. Mantener operaciones en zonas con señales de vida confirmadas."),
    },
    "en": {
        "primary_window":   ("🟢 Primary window (0–72 h)",
                             "Highest statistical probability of live rescue. Prioritize high-priority cells immediately."),
        "secondary_window": ("🟡 Secondary window (72–120 h)",
                             "Reduced but **documented** probability. With air and water access, survival extends. "
                             "INSARAG maintains active operations. Turkey 2023: rescues at +100 h. Focus on confirmed "
                             "reports and confined spaces (basements, stairwells)."),
        "extended_phase":   ("🔵 Extended phase (+120 h)",
                             "Exceptional documented cases: Haiti 2010 (+15 days), Armenia 1988 (+8 days), Mexico 1985 (+14 days). "
                             "Probability is low but real. Maintain operations in areas with confirmed signs of life."),
    },
}

fase_titulo, fase_texto = FASES.get(lang, FASES["es"]).get(fase, ("", ""))
getattr(st, fase_color)(f"**{fase_titulo}**  \n{fase_texto}")

# Métricas y barras de progreso
col1, col2, col3 = st.columns(3)
col1.metric(t("horas_transcurridas", lang), f"{hs:.1f} h")
col2.metric("Ventana principal (72 h)" if lang == "es" else "Primary window (72 h)",
            f"{max(V1 - hs, 0):.1f} h restantes" if hs < V1 else "completada")
col3.metric("Ventana secundaria (120 h)" if lang == "es" else "Secondary window (120 h)",
            f"{max(V2 - hs, 0):.1f} h restantes" if hs < V2 else "completada")

# Barra dual: marca a 72h y 120h
pct_v1 = min(hs / V1, 1.0)
pct_v2 = min(hs / V2, 1.0)
st.caption("Ventana principal (72 h)" if lang == "es" else "Primary window (72 h)")
st.progress(pct_v1)
st.caption("Ventana secundaria (120 h) — INSARAG · Coburn & Spence (2002)" if lang == "es"
           else "Secondary window (120 h) — INSARAG · Coburn & Spence (2002)")
st.progress(pct_v2)

if ctx.get("proyec_ok"):
    st.caption(t("nota_proyeccion", lang))

# --- Peligros secundarios ---
gf = ctx.get("ground_failure") or {}
if gf:
    st.subheader("⚠️ " + t("gf_titulo", lang))
    g = st.columns(2)
    if gf.get("liquefaction_pop"):
        g[0].metric(f"{ALERT_COLORS.get(gf.get('liquefaction_alert'),'')} {t('exposicion_licuefaccion', lang)}",
                    f"{int(gf['liquefaction_pop']):,}")
    if gf.get("landslide_pop"):
        g[1].metric(f"{ALERT_COLORS.get(gf.get('landslide_alert'),'')} {t('exposicion_deslizamiento', lang)}",
                    f"{int(gf['landslide_pop']):,}")
    st.caption(f"🔗 [{config['fuentes']['usgs_ground_failure']['nombre']}]"
               f"({config['fuentes']['usgs_ground_failure']['url']})")

# --- Resumen por zona (cards responsivos con links) ---
st.subheader("🗺️ " + t("resumen_zonas", lang))

zona_rows = resumen.to_dict("records")
col_alta = t("col_celdas_alta", lang)
col_mmi  = t("kpi_mmi_max", lang)

for row, (path, _) in zip(zona_rows, ZONA_PAGES):
    alta    = int(row["alta"])
    mmi_val = f"{row['mmi']:.2f}" if not pd.isna(row["mmi"]) else "—"
    st.markdown('<div class="zona-card">', unsafe_allow_html=True)
    st.page_link(path, label=f"🗺️  {row['nombre']}")
    st.caption(f"{col_alta}: **{alta}** &nbsp;·&nbsp; {col_mmi}: **{mmi_val}**")
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

st.caption(f"🕒 {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")
