"""Personas desaparecidas — búsqueda/registro y casos publicados (fuentes oficiales)."""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.ui import apply_chrome

config = load_config()
lang = apply_chrome(config)
f = config["fuentes"]

st.title("🔎 " + t("desaparecidos_titulo", lang))
st.caption(t("desaparecidos_page_intro", lang))

# ── Registros oficiales de búsqueda (tabla) ───────────────────────────────────
st.subheader("🏛️ " + t("registros_titulo", lang))
st.caption(t("registros_nota", lang))
REG = {
    "es": [
        ("icrc_rfl", "Buscar y registrar familiares (gratuito, confidencial)"),
        ("icrc_trace_face", "Búsqueda con fotos de personas que buscan a su familia"),
        ("cruz_roja_venezolana", "Búsqueda de familiares y ayuda en Venezuela"),
        ("proteccion_civil", "Coordinación de emergencias en Venezuela (171)"),
    ],
    "en": [
        ("icrc_rfl", "Search and register relatives (free, confidential)"),
        ("icrc_trace_face", "Photo-based search for people looking for family"),
        ("cruz_roja_venezolana", "Family search and aid in Venezuela"),
        ("proteccion_civil", "Emergency coordination in Venezuela (171)"),
    ],
}
reg_rows = [{
    t("col_organismo", lang): f[k]["nombre"],
    t("col_ofrece", lang): ofrece,
    t("col_enlace", lang): f[k]["url"],
} for k, ofrece in REG.get(lang, REG["es"]) if k in f]
st.dataframe(pd.DataFrame(reg_rows), width="stretch", hide_index=True,
             column_config={t("col_enlace", lang): st.column_config.LinkColumn(
                 t("col_enlace", lang), display_text="🔗 " + t("abrir", lang))})

# ── Iniciativas ciudadanas (no oficiales, verificadas por prensa) ─────────────
if "desaparecidos_terremoto_ve" in f:
    st.subheader("🤝 " + t("iniciativas_titulo", lang))
    st.caption(t("iniciativas_nota", lang))
    st.markdown(f"🔗 [{f['desaparecidos_terremoto_ve']['nombre']}]"
                f"({f['desaparecidos_terremoto_ve']['url']})")

# ── Casos publicados por fuentes oficiales (solo si existen) ───────────────────
casos = config.get("desaparecidos", []) or []
if casos:
    st.subheader("🧑‍🤝‍🧑 " + t("casos_publicados", lang))
    con_foto = any(c.get("foto_url") for c in casos)
    if con_foto:
        # Tarjetas con foto (si la fuente la publica)
        for i in range(0, len(casos), 3):
            cols = st.columns(3)
            for col, c in zip(cols, casos[i:i + 3]):
                with col:
                    if c.get("foto_url"):
                        st.image(c["foto_url"], use_container_width=True)
                    st.markdown(
                        f"**{c.get('nombre','—')}**"
                        + (f" · {c['edad']}" if c.get("edad") else "")
                        + (f"  \n📍 {c['zona']}" if c.get("zona") else "")
                        + (f"  \n🕒 {c['visto_por_ultima_vez']}" if c.get("visto_por_ultima_vez") else "")
                        + (f"  \n📞 {c['contacto']}" if c.get("contacto") else "")
                        + (f"  \n_{c.get('fuente','')} {c.get('fecha','')}_"
                           + (f" · [{t('abrir', lang)}]({c['url']})" if c.get("url") else "")
                           if c.get("fuente") else ""))
                    st.divider()
    else:
        rows = [{
            t("col_nombre", lang): c.get("nombre", "—"),
            t("col_edad", lang): c.get("edad", "—"),
            t("col_zona", lang): c.get("zona", "—"),
            t("col_visto", lang): c.get("visto_por_ultima_vez", "—"),
            t("col_contacto", lang): c.get("contacto", "—"),
            t("col_enlace", lang): c.get("url", ""),
        } for c in casos]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True,
                     column_config={t("col_enlace", lang): st.column_config.LinkColumn(
                         t("col_enlace", lang), display_text="🔗 " + t("abrir", lang))})
    st.caption("🔗 " + " · ".join(
        f"[{c.get('fuente','fuente')}]({c['url']})" for c in casos if c.get("url")))
