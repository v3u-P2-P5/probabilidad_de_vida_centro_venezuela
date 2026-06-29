"""Router de la app informativa post-terremoto Venezuela 2026.

Usa st.navigation para nombrar la página principal como "Home" y listar las zonas
y secciones. El contenido de inicio vive en home().
"""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.geo import haversine_m
from core.i18n import t
from core.relief import get_gdacs, get_reliefweb_reports
from core.sources import fmt_vet_utc, parse_iso
from core.ui import apply_chrome, render_sources, _cached_zone

st.set_page_config(page_title="Doble Sismo Venezuela 2026", page_icon="🌍", layout="wide")

# Ciudades grandes y conocidas para dar referencia geográfica al público (el
# epicentro real, cerca de Yumare, no le dice nada a la mayoría de la gente).
CIUDADES_REF = {
    "Puerto Cabello": (10.4731, -68.0125),
    "Valencia":       (10.1620, -68.0077),
    "Maracay":        (10.2469, -67.5958),
    "Barquisimeto":   (10.0647, -69.3301),
    "Caracas":        (10.4806, -66.9036),
}


def _ref_ciudad(lat: float, lon: float) -> str:
    """Devuelve 'a ~50 km de Puerto Cabello' usando la gran ciudad más cercana."""
    nombre, dist = min(
        ((n, haversine_m(lat, lon, la, lo) / 1000.0) for n, (la, lo) in CIUDADES_REF.items()),
        key=lambda x: x[1])
    return f"a ~{dist:.0f} km de {nombre}"

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
        _, ctx = _cached_zone(z["id"], _salt)
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
    def _ciudad(lugar: str) -> str:
        """Convierte descripción USGS a español legible.
        '28 km SE of Yumare, Venezuela' → '28 km SE de Yumare'
        """
        if not lugar:
            return ""
        if " of " in lugar:
            direction_part, city_part = lugar.split(" of ", 1)
            city = city_part.replace(", Venezuela", "").strip()
            return f"{direction_part} de {city}"
        return lugar.replace(", Venezuela", "").strip()

    def _km(v) -> str:
        """Profundidad redondeada (USGS a veces da 20.294 → '20 km')."""
        try:
            return f"{float(v):.0f} km"
        except (TypeError, ValueError):
            return "? km"

    def _epicentro_linea(ev: dict) -> None:
        """Epicentro a ancho completo (texto descriptivo que no cabe en un st.metric)."""
        ciudad = _ciudad(ev.get("lugar", ""))
        ref = _ref_ciudad(ev["epicentro"]["lat"], ev["epicentro"]["lon"])
        dist_valencia = haversine_m(ev["epicentro"]["lat"], ev["epicentro"]["lon"],
                                    *CIUDADES_REF["Valencia"]) / 1000.0
        coords = f"{ev['epicentro']['lat']:.2f}, {ev['epicentro']['lon']:.2f}"
        st.markdown(f"**📍 {t('epicentro', lang)}:** {ciudad} · {ref} · "
                    f"a ~{dist_valencia:.0f} km de Valencia · ({coords})")
        st.caption(f"🕒 {fmt_vet_utc(parse_iso(ev['origen_iso']))}"
                   + (f" · 🔗 [{t('evento_real', lang)}]({ev['url']})" if ev.get("url") else ""))

    hs = ctx["hours_since"]
    with st.expander("🌍 Datos del Doble-Sismo", expanded=False):
        if adic:
            a = adic[0]
            st.warning(t("sismo_doble_banner", lang,
                         m1=s.get("id", "us6000t7zp"), mag1=s.get("magnitud", 7.5),
                         m2=a.get("id", "us6000t7zc"), mag2=a.get("magnitud", 7.2)))
        # Fila 1: sismo principal M7.5
        c = st.columns(3)
        c[0].metric(t("magnitud", lang), f"M{s.get('magnitud')}")
        c[1].metric(t("profundidad", lang), _km(s.get("profundidad_km")))
        c[2].metric(t("horas_transcurridas", lang), f"{hs:.0f} h")
        _epicentro_linea(s)
        # Fila 2: sismo secundario M7.2
        if adic:
            a = adic[0]
            c2 = st.columns(3)
            c2[0].metric(t("magnitud", lang), f"M{a.get('magnitud')}")
            c2[1].metric(t("profundidad", lang), _km(a.get("profundidad_km")))
            c2[2].metric("", "")
            _epicentro_linea(a)

    # ── IMPACTO Y CIFRAS ──────────────────────────────────────────────────────
    gd = get_gdacs(config)
    rw = get_reliefweb_reports(config)
    with st.expander("📊 " + t("impacto_titulo", lang), expanded=False):
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
            st.markdown(
                '<p class="swipe-hint">desliza →</p>'
                '<style>@media(max-width:768px){.swipe-hint{'
                'display:block!important;text-align:right;'
                'font-size:0.72rem;color:#aaa;margin:2px 0 0}}'
                '.swipe-hint{display:none}</style>',
                unsafe_allow_html=True,
            )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption("🔗 " + " · ".join(
                f"[{x.get('fuente','fuente')}]({x['url']})" for x in cifras if x.get("url")))

        if rw.get("reports"):
            st.markdown("**" + t("reportes_oficiales", lang) + "**")
            for r in rw["reports"]:
                st.markdown(f"- [{r['title']}]({r['url']}) — *{r['source']}, {r['date']}*")
        else:
            st.caption(t("reportes_oficiales_link", lang, url=rw.get("url", "https://reliefweb.int")))

        upd = []
        if gd.get("datemodified"):
            upd.append(f"GDACS: {gd['datemodified'][:16].replace('T', ' ')}")
        upd.append(f"{t('consulta_fuentes', lang)}: {gd.get('fetched_at', '')}")
        st.caption(t("impacto_nota", lang) + "  ·  " + "  ·  ".join(upd))

    # ── RESPUESTA INTERNACIONAL ───────────────────────────────────────────────
    with st.expander("🌍 Respuesta internacional desplegada", expanded=False):
        rc = st.columns(4)
        rc[0].metric("🌐 Países", "27")
        rc[1].metric("🔍 Equipos USAR", "44")
        rc[2].metric("🧑‍🚒 Rescatistas", "2.245")
        rc[3].metric("🐕 Perros", "140")
        st.warning(
            "⚠️ **El total de OCHA (2.245 rescatistas · 140 perros) es el dato oficial "
            "consolidado de los 44 equipos de 27 países.** Las cifras por país son las "
            "publicadas individualmente — la mayoría no ha dado un desglose detallado, "
            "por eso la suma de la tabla es menor que el total oficial de la ONU."
        )
        _rescate_rows = [
            {"País": "El Salvador",      "🧑‍🚒 Rescatistas": "300", "🐕 Perros": "—"},
            {"País": "Francia",          "🧑‍🚒 Rescatistas": "85",  "🐕 Perros": "—"},
            {"País": "Suiza",            "🧑‍🚒 Rescatistas": "80",  "🐕 Perros": "s/d"},
            {"País": "Reino Unido",      "🧑‍🚒 Rescatistas": "68",  "🐕 Perros": "s/d"},
            {"País": "Turquía",          "🧑‍🚒 Rescatistas": "67",  "🐕 Perros": "—"},
            {"País": "España (UME)",     "🧑‍🚒 Rescatistas": "59",  "🐕 Perros": "8"},
            {"País": "Portugal",         "🧑‍🚒 Rescatistas": "50",  "🐕 Perros": "—"},
            {"País": "Costa Rica",       "🧑‍🚒 Rescatistas": "48",  "🐕 Perros": "—"},
            {"País": "Chile",            "🧑‍🚒 Rescatistas": "46",  "🐕 Perros": "—"},
            {"País": "Brasil",           "🧑‍🚒 Rescatistas": "36",  "🐕 Perros": "6"},
            {"País": "Eslovaquia",       "🧑‍🚒 Rescatistas": "20",  "🐕 Perros": "4"},
            {"País": "Japón",            "🧑‍🚒 Rescatistas": "7",   "🐕 Perros": "—"},
            {"País": "Rep. Dominicana",  "🧑‍🚒 Rescatistas": "s/d", "🐕 Perros": "—"},
            {"País": "Países Bajos",     "🧑‍🚒 Rescatistas": "s/d", "🐕 Perros": "s/d"},
            {"País": "Otros 13 países ✝", "🧑‍🚒 Rescatistas": "s/d", "🐕 Perros": "s/d"},
        ]
        st.markdown('<p class="swipe-hint">desliza →</p>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(_rescate_rows), hide_index=True, use_container_width=True)
        st.caption(
            "✝ Argentina, Canadá, Colombia, Ecuador, Guatemala, México, Panamá, Perú, "
            "Alemania, Rep. Checa, Jordania, Lituania, Qatar · "
            "s/d = sin dato publicado · "
            "Fuente: [OCHA/ONU](https://news.un.org/en/story/2026/06/1167825) · "
            "[Wikipedia](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · 27 jun 2026"
        )

    # ── PERSONAS DESAPARECIDAS ────────────────────────────────────────────────
    st.subheader("🔎 " + t("desaparecidos_titulo", lang))
    st.markdown(t("desaparecidos_texto", lang))
    dcols = st.columns(2)
    for key, col in zip(
        ("desaparecidos_terremoto_ve", "localiza_pacientes",
         "pacientes_terremoto_vzla",   "cruz_roja_venezolana"),
        (dcols[0], dcols[1], dcols[0], dcols[1]),
    ):
        if key in cofu:
            col.markdown(f"🔗 [{cofu[key]['nombre']}]({cofu[key]['url']})")

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

    # ── CÓMO AYUDAR (donaciones) ──────────────────────────────────────────────
    if "centros_acopio_vzla" in cofu or "caritas_venezuela" in cofu:
        st.subheader("💚 " + t("ayudar_titulo", lang))
        if "centros_ayuda_vzla" in cofu:
            st.markdown(f"🔗 [{cofu['centros_ayuda_vzla']['nombre']}]({cofu['centros_ayuda_vzla']['url']})")
        if "caritas_venezuela" in cofu:
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
]
st.navigation(pages).run()
