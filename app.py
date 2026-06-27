"""Página de inicio — Mapa de Probabilidad de Vida (Caracas y La Guaira)."""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.pipeline import build_zone
from core.reports import load_reports
from core.ui import format_quake_time, sidebar_language

st.set_page_config(page_title="Probabilidad de Vida", page_icon="🛰️", layout="wide")

lang = sidebar_language()
config = load_config()

st.title("🛰️ " + t("app_title", lang))
st.caption(t("app_subtitle", lang))
st.markdown(t("intro", lang))


@st.cache_data(ttl=120, show_spinner=False)
def _resumen():
    rows, sismo, hs = [], None, 0.0
    for z in config["zonas"]:
        df, sismo, hs = build_zone(z, config)
        rows.append({
            "id": z["id"], "nombre": z["nombre"],
            "alta": int((df["prioridad"] == "alta").sum()),
            "pob": int(df["pop_present"].sum()),
        })
    return pd.DataFrame(rows), sismo, hs


resumen, sismo, hs = _resumen()
if sismo.get("fuente", "sintético") == "sintético":
    st.warning(t("disclaimer_sintetico", lang))

# --- Evento sísmico ---
st.subheader("📍 " + t("sismo_titulo", lang))
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("magnitud", lang), f"{sismo['magnitud']}")
c2.metric(t("profundidad", lang), f"{sismo.get('profundidad_km', '?')} km")
c3.metric(t("epicentro", lang),
          f"{sismo['epicentro']['lat']:.3f}, {sismo['epicentro']['lon']:.3f}")
c4.metric(t("fuente", lang), sismo.get("fuente", "—"))
st.caption(f"🕒 {t('hora_evento', lang)}: {format_quake_time(sismo)}")

# --- Reloj de las 72 horas de oro ---
st.subheader("⏳ " + t("reloj_titulo", lang))
restantes = max(72.0 - hs, 0.0)
c1, c2 = st.columns(2)
c1.metric(t("horas_transcurridas", lang), f"{hs:.1f} h")
c2.metric(t("horas_restantes", lang), f"{restantes:.1f} h")
st.progress(min(hs / 72.0, 1.0))

# --- Resumen por zona ---
st.subheader("🗺️ " + t("resumen_zonas", lang))
n_reportes = int((load_reports()["estado"].fillna("") != "resuelto").sum()) \
    if not load_reports().empty else 0
view = resumen.rename(columns={
    "nombre": t("col_zona", lang), "alta": t("col_celdas_alta", lang),
    "pob": t("col_poblacion", lang),
})[[t("col_zona", lang), t("col_celdas_alta", lang), t("col_poblacion", lang)]]
st.dataframe(view, width="stretch", hide_index=True)
st.caption(f"📞 {t('kpi_reportes', lang)}: {n_reportes}")
st.info("⬅️ " + t("subtitulo_zona", lang) + " — " + t("nota_modelo", lang))
