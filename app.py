"""Router de la app informativa post-terremoto Venezuela 2026.

Usa st.navigation para nombrar la página principal como "Home" y listar las zonas
y secciones. El contenido de inicio vive en home().
"""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.geo import haversine_m
from core.i18n import fuente_nombre, t
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


def _ref_ciudad(lat: float, lon: float, lang: str = "es") -> str:
    """Devuelve '~50 km de/from Puerto Cabello' usando la gran ciudad más cercana."""
    nombre, dist = min(
        ((n, haversine_m(lat, lon, la, lo) / 1000.0) for n, (la, lo) in CIUDADES_REF.items()),
        key=lambda x: x[1])
    return (f"~{dist:.0f} km from {nombre}" if lang == "en"
            else f"a ~{dist:.0f} km de {nombre}")

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
    st.image("assets/rescatistas.jpg", use_container_width=True)

    # ── NOTA: RÉPLICAS Y RIESGO SÍSMICO ──────────────────────────────────────
    if lang == "en":
        st.info(
            "**📡 Aftershocks in progress — Expert assessment:**\n\n"
            "Since the double earthquake on June 24, **more than 130 aftershocks** have been "
            "recorded (largest M4.8). They are expected and are part of the natural process of "
            "post-rupture crustal stabilization. The USGS estimates a ~40 % probability of a "
            "M6.0+ aftershock in the first week — **these do not signal a new main quake, "
            "but the normal adjustment of the fault**.\n\n"
            "**The probability of a new earthquake of comparable magnitude (M7+) in the coming "
            "hours or days is extremely low.** The June 24 event was the most intense in "
            "Venezuela in **126 years** (since San Narciso, 1900): events of this magnitude are "
            "extremely rare in the same area. Seismologists note that, with the energy "
            "accumulated over more than a century in the Boconó fault system now released, "
            "an immediate repeat has no physical basis. FUNVISIS and USGS monitor seismic "
            "activity continuously and in real time.\n\n"
            "🧭 **Follow post-earthquake safety precautions** — especially regarding damaged "
            "structures that may collapse during minor aftershocks.\n\n"
            "📌 *Sources: "
            "[USGS · Miyamoto International](https://miyamotointernational.com/venezuelas-strongest-earthquake-in-125-years-what-happened-on-june-24-2026/) · "
            "[Wikipedia EN](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
            "[SkyAlert MX](https://skyalert.mx/articulos/actualizacion-sismos-venezuela-2026) · "
            "[Ecoosfera — plate tectonics](https://ecoosfera.com/noticias/sismos-venezuela-2026-teoria-placas/)*"
        )
    else:
        st.info(
            "**📡 Réplicas en curso — Opinión de los expertos:**\n\n"
            "Desde el doble sismo del 24 de junio se han registrado **más de 130 réplicas** "
            "(la mayor en M4.8). Son esperables y forman parte del proceso natural de "
            "estabilización cortical post-ruptura. El USGS estima ~40 % de probabilidad de "
            "una réplica M6.0+ durante la primera semana — **no indican un nuevo sismo "
            "principal, sino el ajuste normal de la falla**.\n\n"
            "**La probabilidad de un nuevo sismo de magnitud comparable (M7+) en las próximas "
            "horas o días es sumamente baja.** El evento del 24 de junio fue el más intenso en "
            "Venezuela en **126 años** (desde San Narciso, 1900): eventos de esta magnitud son "
            "extremadamente infrecuentes en la misma zona. Los sismólogos señalan que, "
            "liberada la energía acumulada durante más de un siglo en el sistema de fallas de "
            "Boconó, una repetición inmediata carece de base física. FUNVISIS y el USGS "
            "monitorean la actividad de forma continua y en tiempo real.\n\n"
            "🧭 **Sigue las precauciones post-terremoto** — especialmente respecto a estructuras "
            "dañadas que pueden colapsar con réplicas menores.\n\n"
            "📌 *Fuentes: "
            "[USGS · Miyamoto International](https://miyamotointernational.com/venezuelas-strongest-earthquake-in-125-years-what-happened-on-june-24-2026/) · "
            "[Wikipedia EN](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
            "[SkyAlert MX](https://skyalert.mx/articulos/actualizacion-sismos-venezuela-2026) · "
            "[Ecoosfera — teoría de placas](https://ecoosfera.com/noticias/sismos-venezuela-2026-teoria-placas/)*"
        )
    st.page_link("pages/5_Consejos_post_terremoto.py", label="🧭 " + t("ver_consejos", lang) + " →")

    # ── Evento (compacto) ─────────────────────────────────────────────────────
    s = ctx["sismo"]
    adic = ctx.get("sismos_adicionales", [])
    def _ciudad(lugar: str) -> str:
        """Limpia descripción USGS; en español convierte 'of' → 'de'."""
        if not lugar:
            return ""
        lugar = lugar.replace(", Venezuela", "").strip()
        if lang != "en" and " of " in lugar:
            parts = lugar.split(" of ", 1)
            return f"{parts[0]} de {parts[1]}"
        return lugar

    def _km(v) -> str:
        """Profundidad redondeada (USGS a veces da 20.294 → '20 km')."""
        try:
            return f"{float(v):.0f} km"
        except (TypeError, ValueError):
            return "? km"

    def _epicentro_linea(ev: dict) -> None:
        """Epicentro a ancho completo (texto descriptivo que no cabe en un st.metric)."""
        ciudad = _ciudad(ev.get("lugar", ""))
        ref = _ref_ciudad(ev["epicentro"]["lat"], ev["epicentro"]["lon"], lang)
        dist_valencia = haversine_m(ev["epicentro"]["lat"], ev["epicentro"]["lon"],
                                    *CIUDADES_REF["Valencia"]) / 1000.0
        coords = f"{ev['epicentro']['lat']:.2f}, {ev['epicentro']['lon']:.2f}"
        valencia_ref = (f"~{dist_valencia:.0f} km from Valencia"
                        if lang == "en" else f"a ~{dist_valencia:.0f} km de Valencia")
        st.markdown(f"**📍 {t('epicentro', lang)}:** {ciudad} · {ref} · "
                    f"{valencia_ref} · ({coords})")
        st.caption(f"🕒 {fmt_vet_utc(parse_iso(ev['origen_iso']))}"
                   + (f" · 🔗 [{t('evento_real', lang)}]({ev['url']})" if ev.get("url") else ""))

    hs = ctx["hours_since"]
    with st.expander(t("expander_sismo_doble", lang), expanded=False):
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
                f'<p class="swipe-hint">{t("swipe_hint", lang)}</p>'
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
    with st.expander(t("expander_respuesta_intl", lang), expanded=False):
        rc = st.columns(4)
        _paises_lbl    = "🌐 Countries"     if lang == "en" else "🌐 Países"
        _equipos_lbl   = "🔍 USAR Teams"    if lang == "en" else "🔍 Equipos USAR"
        _rescatist_lbl = "🧑‍🚒 Rescue Workers" if lang == "en" else "🧑‍🚒 Rescatistas"
        _perros_lbl    = "🐕 Dogs"           if lang == "en" else "🐕 Perros"
        rc[0].metric(_paises_lbl,    "27")
        rc[1].metric(_equipos_lbl,   "44")
        rc[2].metric(_rescatist_lbl, "2,245" if lang == "en" else "2.245")
        rc[3].metric(_perros_lbl,    "140")
        _na = "n/a" if lang == "en" else "s/d"
        if lang == "en":
            st.warning(
                "⚠️ **The OCHA total (2,245 rescue workers · 140 dogs) is the official "
                "consolidated figure from all 44 teams across 27 countries.** Individual "
                "country figures are those published separately — most have not released "
                "detailed breakdowns, which is why the table sum is lower than the UN total."
            )
            _col_pais = "Country"
            _col_resc = "🧑‍🚒 Rescue Workers"
            _col_perr = "🐕 Dogs"
            _otros    = "Other 13 countries ✝"
        else:
            st.warning(
                "⚠️ **El total de OCHA (2.245 rescatistas · 140 perros) es el dato oficial "
                "consolidado de los 44 equipos de 27 países.** Las cifras por país son las "
                "publicadas individualmente — la mayoría no ha dado un desglose detallado, "
                "por eso la suma de la tabla es menor que el total oficial de la ONU."
            )
            _col_pais = "País"
            _col_resc = "🧑‍🚒 Rescatistas"
            _col_perr = "🐕 Perros"
            _otros    = "Otros 13 países ✝"
        _rescate_rows = [
            {_col_pais: "El Salvador",   _col_resc: "300", _col_perr: "—"},
            {_col_pais: "France" if lang == "en" else "Francia",
                                         _col_resc: "85",  _col_perr: "—"},
            {_col_pais: "Switzerland" if lang == "en" else "Suiza",
                                         _col_resc: "80",  _col_perr: _na},
            {_col_pais: "United Kingdom" if lang == "en" else "Reino Unido",
                                         _col_resc: "68",  _col_perr: _na},
            {_col_pais: "Turkey" if lang == "en" else "Turquía",
                                         _col_resc: "67",  _col_perr: "—"},
            {_col_pais: "Spain (UME)" if lang == "en" else "España (UME)",
                                         _col_resc: "59",  _col_perr: "8"},
            {_col_pais: "Portugal",      _col_resc: "50",  _col_perr: "—"},
            {_col_pais: "Costa Rica",    _col_resc: "48",  _col_perr: "—"},
            {_col_pais: "Chile",         _col_resc: "46",  _col_perr: "—"},
            {_col_pais: "Brazil" if lang == "en" else "Brasil",
                                         _col_resc: "36",  _col_perr: "6"},
            {_col_pais: "Slovakia" if lang == "en" else "Eslovaquia",
                                         _col_resc: "20",  _col_perr: "4"},
            {_col_pais: "Japan" if lang == "en" else "Japón",
                                         _col_resc: "7",   _col_perr: "—"},
            {_col_pais: "Dominican Rep." if lang == "en" else "Rep. Dominicana",
                                         _col_resc: _na,   _col_perr: "—"},
            {_col_pais: "Netherlands" if lang == "en" else "Países Bajos",
                                         _col_resc: _na,   _col_perr: _na},
            {_col_pais: _otros,          _col_resc: _na,   _col_perr: _na},
        ]
        st.markdown(f'<p class="swipe-hint">{t("swipe_hint", lang)}</p>',
                    unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(_rescate_rows), hide_index=True, use_container_width=True)
        if lang == "en":
            st.caption(
                "✝ Argentina, Canada, Colombia, Ecuador, Guatemala, Mexico, Panama, Peru, "
                "Germany, Czech Rep., Jordan, Lithuania, Qatar · "
                "n/a = no figure published · "
                "Source: [OCHA/UN](https://news.un.org/en/story/2026/06/1167825) · "
                "[Wikipedia](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · 27 Jun 2026"
            )
        else:
            st.caption(
                "✝ Argentina, Canadá, Colombia, Ecuador, Guatemala, México, Panamá, Perú, "
                "Alemania, Rep. Checa, Jordania, Lituania, Qatar · "
                "s/d = sin dato publicado · "
                "Fuente: [OCHA/ONU](https://news.un.org/en/story/2026/06/1167825) · "
                "[Wikipedia](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · 27 jun 2026"
            )

    # ── RÉPLICAS ──────────────────────────────────────────────────────────────
    with st.expander(t("expander_replicas", lang), expanded=False):
        if lang == "en":
            st.markdown(
                "Since the double earthquake on **24 Jun 2026**, **more than 130 aftershocks** "
                "have been recorded. Aftershocks are normal adjustments of the Earth's crust "
                "following a major rupture and decrease in frequency and intensity over time."
            )
            _replicas = [
                {"Date": "26 Jun 2026", "Magnitude": "M4.7", "Area": "La Guaira",
                 "Note": "Bridge collapse in Caraballeda; additional damage in Caracas"},
                {"Date": "29 Jun 2026", "Magnitude": "M4.6", "Area": "N. Venezuela",
                 "Note": "Felt in Caracas and coastal area"},
                {"Date": "24–29 Jun",   "Magnitude": "≤M4.8", "Area": "Epicentral region",
                 "Note": "130+ aftershocks recorded; largest M4.8 (USGS)"},
            ]
            st.dataframe(pd.DataFrame(_replicas), hide_index=True, use_container_width=True)
            st.markdown("**USGS forecast (first week):**")
            _pronostico = [
                {"Threshold": "M5.0+", "Estimated probability": "~100 % (near certain)", "Meaning": "Several expected"},
                {"Threshold": "M6.0+", "Estimated probability": "~40 %",                 "Meaning": "Possible, not certain"},
                {"Threshold": "M7.0+", "Estimated probability": "Very low",               "Meaning": "Extremely unlikely"},
            ]
        else:
            st.markdown(
                "Tras el doble sismo del **24 jun 2026** se han registrado **más de 130 réplicas**. "
                "Las réplicas son ajustes normales de la corteza terrestre después de una ruptura "
                "mayor y disminuyen en frecuencia e intensidad con el tiempo."
            )
            _replicas = [
                {"Fecha": "26 jun 2026", "Magnitud": "M4.7", "Zona": "La Guaira",
                 "Nota": "Colapso de puente en Caraballeda; daños adicionales en Caracas"},
                {"Fecha": "29 jun 2026", "Magnitud": "M4.6", "Zona": "Norte de Venezuela",
                 "Nota": "Sentida en Caracas y zona costera"},
                {"Fecha": "24–29 jun",   "Magnitud": "≤M4.8", "Zona": "Región epicentral",
                 "Nota": "Más de 130 réplicas registradas; mayor en M4.8 (USGS)"},
            ]
            st.dataframe(pd.DataFrame(_replicas), hide_index=True, use_container_width=True)
            st.markdown("**Pronóstico USGS (primera semana):**")
            _pronostico = [
                {"Umbral": "M5.0+", "Probabilidad estimada": "~100 % (casi certeza)", "Significado": "Esperables varias"},
                {"Umbral": "M6.0+", "Probabilidad estimada": "~40 %",                 "Significado": "Posible, no segura"},
                {"Umbral": "M7.0+", "Probabilidad estimada": "Muy baja",              "Significado": "Extremadamente improbable"},
            ]
        st.dataframe(pd.DataFrame(_pronostico), hide_index=True, use_container_width=True)
        _src_lbl = "Sources" if lang == "en" else "Fuentes"
        st.caption(
            f"{_src_lbl}: "
            "[USGS · Miyamoto International](https://miyamotointernational.com/venezuelas-strongest-earthquake-in-125-years-what-happened-on-june-24-2026/) · "
            "[Wikipedia EN](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
            "[Univision (29 jun)](https://www.univision.com/noticias/america-latina/ultimas-noticias-del-terremoto-en-venezuela-un-nuevo-sismo-de-4-2-vuelve-a-impactar-la-zona-norte-de-venezuela-en-medio-de-la-busqueda-de-mas-de-50-000-personas-atrapadas-hoy-29-de-junio-de-2026)"
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
            col.markdown(f"🔗 [{fuente_nombre(cofu[key], lang)}]({cofu[key]['url']})")

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
    st.image("assets/perros.png", use_container_width=True)

    # ── CÓMO AYUDAR (donaciones) ──────────────────────────────────────────────
    if "centros_acopio_vzla" in cofu or "caritas_venezuela" in cofu:
        st.subheader("💚 " + t("ayudar_titulo", lang))
        if "centros_ayuda_vzla" in cofu:
            st.markdown(f"🔗 [{fuente_nombre(cofu['centros_ayuda_vzla'], lang)}]({cofu['centros_ayuda_vzla']['url']})")
        if "caritas_venezuela" in cofu:
            st.markdown(f"🔗 [{fuente_nombre(cofu['caritas_venezuela'], lang)}]({cofu['caritas_venezuela']['url']})")

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
