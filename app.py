"""Página de inicio — Mapa de Probabilidad de Sobrevivientes (Caracas y La Guaira)."""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.pipeline import build_zone
from core.reports import load_reports
from core.sources import fmt_vet_utc, parse_iso
from core.ui import ALERT_COLORS, apply_chrome, render_sources

st.set_page_config(page_title="Probabilidad de Sobrevivientes", page_icon="🛰️", layout="wide")

config = load_config()
lang = apply_chrome(config)


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

st.title("🛰️ " + t("app_title", lang))
st.caption(t("app_subtitle", lang))
(st.error if ctx["modo"] == "operativo" else st.warning)(
    t("modo_operativo_label" if ctx["modo"] == "operativo" else "modo_demo_label", lang))
st.markdown(t("intro", lang))

# --- Secuencia sísmica (sismo doble) ---
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
    if adicionales:
        a = adicionales[0]
        if a.get("url"):
            st.caption(f"🔗 [{t('sismo_secundario', lang)} M{a.get('magnitud')}]({a['url']})")

# Actualización en tiempo real
st.caption(t("actualizacion_tiempo_real", lang))

# --- Reloj 72h ---
st.subheader("⏳ " + t("reloj_titulo", lang))
hs = ctx["hours_since"]
if hs >= 72:
    st.error(t("ventana_agotada", lang))
else:
    st.info(t("alerta_ventana72", lang))
cc = st.columns(2)
cc[0].metric(t("horas_transcurridas", lang), f"{hs:.1f} h")
cc[1].metric(t("horas_restantes", lang), f"{max(72 - hs, 0):.1f} h")
st.progress(min(hs / 72.0, 1.0))

# --- Proyecciones estadísticas activas ---
if ctx.get("proyec_ok"):
    st.caption(t("nota_proyeccion", lang))

# --- Peligros secundarios (USGS ground-failure) ---
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

# --- Resumen por zona ---
st.subheader("🗺️ " + t("resumen_zonas", lang))
view = resumen.rename(columns={"nombre": t("col_zona", lang),
                               "alta": t("col_celdas_alta", lang),
                               "mmi": t("kpi_mmi_max", lang)})
st.dataframe(view, width="stretch", hide_index=True)
reps = load_reports()
n_rep = int((reps["estado"].fillna("") != "resuelto").sum()) if not reps.empty else 0
st.caption(f"📞 {t('kpi_reportes', lang)}: {n_rep}  ·  {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")
st.info("⬅️ " + t("subtitulo_zona", lang) + " — " + t("nota_modelo", lang))
