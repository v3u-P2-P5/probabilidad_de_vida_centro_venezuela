"""Ingreso de reportes de campo en tiempo real (eleva la prioridad de celdas)."""
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.reports import append_report, load_reports
from core.ui import sidebar_language

st.set_page_config(page_title="Reportes de campo", page_icon="📞", layout="wide")

lang = sidebar_language()
config = load_config()
zonas = {z["id"]: z["nombre"] for z in config["zonas"]}

st.title("📞 " + t("reportes_titulo", lang))
st.caption(t("reportes_intro", lang))

with st.form("reporte", clear_on_submit=True):
    c1, c2 = st.columns(2)
    zona_id = c1.selectbox(t("form_zona", lang), list(zonas.keys()),
                           format_func=lambda k: zonas[k])
    fuente = c2.text_input(t("form_fuente", lang), value="")
    c3, c4, c5 = st.columns(3)
    lat = c3.number_input(t("form_lat", lang), value=10.50, format="%.5f")
    lon = c4.number_input(t("form_lon", lang), value=-66.90, format="%.5f")
    personas = c5.number_input(t("form_personas", lang), min_value=0, value=1, step=1)
    c6, c7 = st.columns(2)
    confianza = c6.slider(t("form_confianza", lang), 0.0, 1.0, 0.7, 0.05)
    estado = c7.selectbox(t("form_estado", lang),
                          ["nuevo", "en proceso", "resuelto"],
                          format_func=lambda s: t(f"estado_{s.replace(' ', '_')}", lang))
    nota = st.text_area(t("form_nota", lang), value="")
    enviado = st.form_submit_button(t("form_enviar", lang))

if enviado:
    append_report({
        "zona": zona_id, "lat": lat, "lon": lon,
        "personas_estimadas": int(personas), "fuente": fuente,
        "confianza": confianza, "estado": estado, "nota": nota,
    })
    st.cache_data.clear()
    st.success(t("guardado_ok", lang))

st.subheader(t("reportes_existentes", lang))
reportes = load_reports()
if reportes.empty:
    st.info(t("sin_reportes", lang))
else:
    st.dataframe(reportes.iloc[::-1], width="stretch", hide_index=True)
