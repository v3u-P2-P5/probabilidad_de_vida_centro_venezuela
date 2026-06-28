"""Router de la app informativa post-terremoto Venezuela 2026.

Usa st.navigation para nombrar la página principal como "Home" y listar las zonas
y secciones. El contenido de inicio vive en home().
"""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.i18n import t
from core.pipeline import build_zone
from core.relief import get_gdacs, get_reliefweb_reports
from core.sources import fmt_vet_utc, parse_iso
from core.ui import apply_chrome, render_sources

st.set_page_config(page_title="Doble Sismo Venezuela 2026", page_icon="🌍", layout="wide")

config = load_config()

ZONA_PAGES = [
    ("pages/1_Caracas_Libertador.py",       "Libertador"),
    ("pages/2_Caracas_Sucre_Petare.py",     "Sucre / Petare"),
    ("pages/3_Caracas_Baruta_ElHatillo.py", "Baruta / Hatillo / Chacao"),
    ("pages/4_La_Guaira_Litoral.py",        "La Guaira"),
]


@st.cache_data(ttl=300, show_spinner=True)
def _resumen(_salt: int):
    rows, ctx = [], None
    for z in config["zonas"]:
        _, ctx = build_zone(z, config, with_osm=False)
        rows.append({"nombre": z["nombre"],
                     "mmi": ctx.get("mmi_max"),
                     "pob": ctx.get("poblacion_total")})
    return pd.DataFrame(rows), ctx


def home():
    lang = apply_chrome(config)
    resumen, ctx = _resumen(config.get("autorefresco_segundos", 0))
    render_sources(ctx, lang)
    cofu = config["fuentes"]

    st.title(t("app_title", lang))
    st.caption(t("app_subtitle", lang))

    # ── Evento (compacto) ─────────────────────────────────────────────────────
    s = ctx["sismo"]
    adic = ctx.get("sismos_adicionales", [])
    if adic:
        a = adic[0]
        st.warning(t("sismo_doble_banner", lang,
                     m1=s.get("id", "us6000t7zp"), mag1=s.get("magnitud", 7.5),
                     m2=a.get("id", "us6000t7zc"), mag2=a.get("magnitud", 7.2)))
    hs = ctx["hours_since"]
    c = st.columns(4)
    # Fila 1: datos del sismo principal (M7.5)
    c[0].metric(t("magnitud", lang), f"M{s.get('magnitud')}")
    c[1].metric(t("profundidad", lang), f"{s.get('profundidad_km','?')} km")
    c[2].metric(t("epicentro", lang), f"{s['epicentro']['lat']:.2f}, {s['epicentro']['lon']:.2f}")
    c[3].metric(t("horas_transcurridas", lang), f"{hs:.0f} h")
    st.caption(f"📌 {s.get('lugar','')} · 🕒 {fmt_vet_utc(parse_iso(s['origen_iso']))}"
               + (f" · 🔗 [{t('evento_real', lang)}]({s['url']})" if s.get("url") else ""))
    # Fila 2: sismo secundario (M7.2) con sus propios datos
    if adic:
        a = adic[0]
        c2 = st.columns(4)
        c2[0].metric(t("magnitud", lang), f"M{a.get('magnitud')}")
        c2[1].metric(t("profundidad", lang), f"{a.get('profundidad_km','?')} km")
        c2[2].metric(t("epicentro", lang),
                     f"{a['epicentro']['lat']:.2f}, {a['epicentro']['lon']:.2f}")
        c2[3].metric("", "")   # espacio; las horas son las mismas
        st.caption(f"📌 {a.get('lugar','')} · 🕒 {fmt_vet_utc(parse_iso(a['origen_iso']))}"
                   + (f" · 🔗 [{t('evento_real', lang)}]({a['url']})" if a.get("url") else ""))

    # ── IMPACTO Y CIFRAS ──────────────────────────────────────────────────────
    st.subheader("📊 " + t("impacto_titulo", lang))
    gd = get_gdacs(config)
    rw = get_reliefweb_reports(config)

    # Cifras reportadas por fuente (tabla atribuida)
    cifras = config.get("cifras_oficiales", [])
    if cifras:
        st.markdown("**" + t("cifras_titulo", lang) + "**")
        st.warning(t("cifras_disclaimer", lang))
        rows = [{
            t("col_fuente", lang): x.get("fuente", ""),
            t("col_fecha", lang): x.get("fecha", ""),
            t("col_fallecidos", lang): x.get("fallecidos", "—"),
            t("col_heridos", lang): x.get("heridos", "—"),
            t("col_desaparecidos", lang): x.get("desaparecidos", "—"),
            t("col_notas", lang): x.get("notas", ""),
        } for x in cifras]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("🔗 " + " · ".join(
            f"[{x.get('fuente','fuente')}]({x['url']})" for x in cifras if x.get("url")))

    # Reportes oficiales OCHA/ReliefWeb
    if rw.get("reports"):
        st.markdown("**" + t("reportes_oficiales", lang) + "**")
        for r in rw["reports"]:
            st.markdown(f"- [{r['title']}]({r['url']}) — *{r['source']}, {r['date']}*")
    else:
        st.caption(t("reportes_oficiales_link", lang, url=rw.get("url", "https://reliefweb.int")))

    # Última actualización de las fuentes
    upd = []
    if gd.get("datemodified"):
        upd.append(f"GDACS: {gd['datemodified'][:16].replace('T', ' ')}")
    upd.append(f"{t('consulta_fuentes', lang)}: {gd.get('fetched_at', '')}")
    st.caption(t("impacto_nota", lang) + "  ·  " + "  ·  ".join(upd))

    # ── PERSONAS DESAPARECIDAS ────────────────────────────────────────────────
    st.subheader("🔎 " + t("desaparecidos_titulo", lang))
    st.markdown(t("desaparecidos_texto", lang))
    dcols = st.columns(2)
    if "icrc_rfl" in cofu:
        dcols[0].markdown(f"🔗 [{cofu['icrc_rfl']['nombre']}]({cofu['icrc_rfl']['url']})")
    if "cruz_roja_venezolana" in cofu:
        dcols[1].markdown(f"🔗 [{cofu['cruz_roja_venezolana']['nombre']}]({cofu['cruz_roja_venezolana']['url']})")
    st.page_link("pages/6_Personas_desaparecidas.py", label="🔎 " + t("ver_desaparecidos", lang))

    # ── ENCUENTRA AYUDA EN TU ZONA (color por intensidad) ─────────────────────
    st.subheader("🆘 " + t("ayuda_zona_titulo", lang))
    st.caption(t("ayuda_zona_nota", lang))
    recs = resumen.to_dict("records")
    mmis = [r["mmi"] for r in recs if pd.notna(r["mmi"])]
    mlo, mhi = (min(mmis), max(mmis)) if mmis else (0, 1)

    def _color(mmi):
        # Todas las zonas están afectadas: escala rojo (más) → naranja (menos).
        # Nunca verde (verde sugeriría "están bien", inapropiado en emergencia).
        if pd.isna(mmi) or mhi - mlo < 1e-9:
            return "hsl(20, 80%, 45%)"
        frac = (mmi - mlo) / (mhi - mlo)      # 1 = mayor intensidad
        return f"hsl({int(35 * (1 - frac))}, 85%, 45%)"   # 0 rojo → 35 naranja

    pairs = list(zip(recs, ZONA_PAGES))
    for i in range(0, len(pairs), 2):
        ccs = st.columns(2, gap="medium")
        for j, col in enumerate(ccs):
            if i + j >= len(pairs):
                break
            row, (path, _) = pairs[i + j]
            mmi = f"{row['mmi']:.1f}" if pd.notna(row["mmi"]) else "—"
            pob = f"{int(row['pob']):,}" if pd.notna(row["pob"]) else "—"
            color = _color(row["mmi"])
            with col:
                st.markdown(f"""
<div style="border:2px solid {color};border-left:10px solid {color};border-radius:12px;
  padding:12px 14px 8px;background:rgba(0,0,0,0.03);margin-bottom:4px;">
  <div style="font-size:1.05rem;font-weight:700;color:{color};">📍 {row['nombre']}</div>
  <div style="font-size:0.82rem;color:#555;">{t('kpi_mmi_max', lang)}: <b>{mmi}</b>
    &nbsp;·&nbsp; {t('kpi_poblacion_residente', lang)}: <b>{pob}</b></div>
</div>""", unsafe_allow_html=True)
                st.page_link(path, label="🆘 " + t("ver_ayuda_zona", lang))
    st.caption(t("leyenda_zonas", lang))

    # ── DAÑOS MATERIALES Y MAPAS OFICIALES (sección unificada) ────────────────
    st.subheader("🛰️ " + t("danos_titulo", lang))
    danos = config.get("danos_materiales", [])
    if danos:
        drows = [{
            t("col_descripcion", lang): d.get("texto", ""),
            t("col_fuente", lang): d.get("fuente", ""),
            t("col_actualizado", lang): d.get("fecha", ""),
            t("col_enlace", lang): d.get("url", ""),
        } for d in danos]
        st.dataframe(pd.DataFrame(drows), width="stretch", hide_index=True,
                     column_config={t("col_enlace", lang): st.column_config.LinkColumn(
                         t("col_enlace", lang), display_text="🔗 " + t("abrir", lang))})
    st.markdown(t("danos_texto", lang))
    for k in ("copernicus_emsr884", "unosat", "maxar_open_data"):
        if k in cofu:
            st.markdown(f"🔗 [{cofu[k]['nombre']}]({cofu[k]['url']})")

    # ── CÓMO AYUDAR (donaciones) ──────────────────────────────────────────────
    if "caritas_venezuela" in cofu:
        st.subheader("💚 " + t("ayudar_titulo", lang))
        st.markdown(f"🔗 [{cofu['caritas_venezuela']['nombre']}]({cofu['caritas_venezuela']['url']})")

    # ── CONSEJOS POST-TERREMOTO (página aparte) ───────────────────────────────
    st.subheader("🧭 " + t("consejos_titulo", lang))
    st.page_link("pages/5_Consejos_post_terremoto.py", label="🧭 " + t("ver_consejos", lang))

    st.caption(f"🕒 {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")


# ── Navegación (la página principal se muestra como "Home") ───────────────────
pages = [
    st.Page(home, title="Home", icon="🏠", default=True),
    st.Page("pages/1_Caracas_Libertador.py",       title="Caracas — Libertador", icon="📍"),
    st.Page("pages/2_Caracas_Sucre_Petare.py",     title="Caracas — Sucre / Petare", icon="📍"),
    st.Page("pages/3_Caracas_Baruta_ElHatillo.py", title="Caracas — Baruta / Hatillo / Chacao", icon="📍"),
    st.Page("pages/4_La_Guaira_Litoral.py",        title="La Guaira — Litoral", icon="📍"),
    st.Page("pages/5_Consejos_post_terremoto.py",  title="Consejos post-terremoto", icon="🧭"),
    st.Page("pages/6_Personas_desaparecidas.py",   title="Personas desaparecidas", icon="🔎"),
]
st.navigation(pages).run()
