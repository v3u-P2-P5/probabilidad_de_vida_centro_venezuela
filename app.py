"""Router de la app informativa post-terremoto Venezuela 2026.

Usa st.navigation para nombrar la página principal como "Home" y listar las zonas
y secciones. El contenido de inicio vive en home().
"""
import pandas as pd
import streamlit as st

from core.config import load_config
from core.geo import haversine_m
from core.i18n import fmt_int, fuente_nombre, t
from core.relief import get_gdacs, get_reliefweb_reports
from core.sources import fecha_larga_vet, fmt_fecha_corta, fmt_vet_utc, parse_iso
from core.ui import apply_chrome, render_sources, _cached_zone

st.set_page_config(page_title="Venezuela 2026 — Doble Sismo / Double Earthquake", page_icon="🌎", layout="wide")

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
        # with_osm=False: el Home solo necesita MMI y población, no los recursos
        # OSM → evita 4 POST en serie a Overpass que bloqueaban la carga inicial.
        _, ctx = _cached_zone(z["id"], _salt, with_osm=False)
        rows.append({"nombre": z["nombre"],
                     "mmi": ctx.get("mmi_max"),
                     "pob": ctx.get("poblacion_total")})
    return pd.DataFrame(rows), ctx


def home():
    lang = apply_chrome(config)
    resumen, ctx = _resumen(config.get("autorefresco_segundos", 0))
    render_sources(ctx, lang)
    cofu = config["fuentes"]

    # Letra general más grande y legible en Home; las citas/fuentes (st.caption)
    # se mantienen en su tamaño pequeño actual explícitamente.
    st.markdown("""
<style>
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] p {
    font-size: 1.08rem !important;
    line-height: 1.65 !important;
}
.stCaption, [data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    font-size: 0.8rem !important;
    line-height: 1.4 !important;
}
</style>
""", unsafe_allow_html=True)

    st.title(t("app_title", lang))
    st.markdown(f'<p style="font-size:1.2rem;opacity:0.85;">{t("app_subtitle", lang)}</p>',
                unsafe_allow_html=True)
    st.image("assets/caritas.webp", use_container_width=True,
             caption=f"{t('img_caritas', lang)} — {fecha_larga_vet(lang)}")

    # ── IMPACTO Y CIFRAS (sección más importante: siempre visible, sin desplegable) ──
    st.subheader("📊 " + t("impacto_titulo", lang))
    gd = get_gdacs(config)
    rw = get_reliefweb_reports(config)
    cifras = config.get("cifras_oficiales", [])
    if cifras:
        st.markdown("**" + t("cifras_titulo", lang) + "**")
        st.warning(t("cifras_disclaimer", lang))
        for x in cifras:
            _notas_html = (
                f'<div style="font-size:1rem;color:var(--text-color,#1a1a1a);'
                f'opacity:0.9;margin-top:6px;">{x.get("notas", "")}</div>'
                if x.get("notas") else ""
            )
            _campos = [
                (t("col_fallecidos", lang), x.get("fallecidos")),
                (t("col_heridos", lang), x.get("heridos")),
                (t("col_desaparecidos", lang), x.get("desaparecidos")),
                (t("col_desplazados", lang), x.get("desplazados")),
            ]
            _cifras_html = "<br>".join(
                f'<span style="font-size:1.05rem;">{label}:</span> '
                f'<span style="font-size:1.4rem;font-weight:800;">{valor}</span>'
                for label, valor in _campos if valor
            )
            _fecha_fmt = fmt_fecha_corta(x.get("fecha", ""), lang)
            st.markdown(f"""
<div style="border:1px solid var(--border-color,#e6dada);border-left:6px solid #b3261e;
  border-radius:10px;padding:10px 14px;margin-bottom:10px;
  background:var(--secondary-background-color,#f5f0ef);">
  <div style="font-weight:700;font-size:1.1rem;color:var(--text-color,#1a1a1a);">{x.get('fuente', '')}</div>
  <div style="font-size:0.78rem;color:var(--text-color,#1a1a1a);opacity:0.7;margin-bottom:6px;">{_fecha_fmt}</div>
  <div style="line-height:1.9;color:var(--text-color,#1a1a1a);">
    {_cifras_html}
  </div>
  {_notas_html}
</div>""", unsafe_allow_html=True)
        st.caption("🔗 " + " · ".join(
            f"[{x.get('fuente','fuente')}]({x['url']})" for x in cifras if x.get("url")))

    st.markdown("**" + t("damnificados_stats_titulo", lang) + "**")
    _dc_items = [
        (t("damnificados_sin_hogar", lang), "~16.000" if lang == "es" else "~16,000"),
        (t("damnificados_afectados", lang), "~6,76 M" if lang == "es" else "~6.76 M"),
        (t("damnificados_en_calle", lang),  "39 %"),
    ]
    _dc_html = "".join(
        f'<div style="flex:1 1 0;min-width:120px;text-align:center;padding:6px 4px;">'
        f'<div style="font-size:0.95rem;color:var(--text-color,#1a1a1a);opacity:0.85;">{label}</div>'
        f'<div style="font-size:1.6rem;font-weight:800;color:var(--text-color,#1a1a1a);">{valor}</div>'
        f"</div>"
        for label, valor in _dc_items
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:4px;'
        f'border:1px solid var(--border-color,#e6dada);border-radius:10px;'
        f'padding:10px 6px;background:var(--secondary-background-color,#f5f0ef);">'
        f"{_dc_html}</div>",
        unsafe_allow_html=True,
    )
    st.caption(t("damnificados_stats_nota", lang))

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
    st.divider()

    # ── RÉPLICAS + OPINIÓN DE EXPERTOS (primera sección desplegable) ─────────
    with st.expander(t("expander_replicas", lang), expanded=False):
        if lang == "en":
            st.markdown(
                "Since the double earthquake on **24 Jun 2026**, **more than 782 aftershocks** "
                "have been recorded (largest M4.8). They are expected and are part of the natural "
                "process of post-rupture crustal stabilization."
            )
            _replicas = [
                {"Date": "2026-jun-26", "Magnitude": "M4.7", "Area": "La Guaira",
                 "Note": "Bridge collapse in Caraballeda; additional damage in Caracas"},
                {"Date": "2026-jun-29", "Magnitude": "M4.6", "Area": "N. Venezuela",
                 "Note": "Felt in Caracas and coastal area"},
                {"Date": "2026-jun-24 – 2026-jul-01",   "Magnitude": "≤M4.8", "Area": "Epicentral region",
                 "Note": "782+ aftershocks recorded; largest M4.8 (Nat'l Assembly, Jul 1)"},
            ]
            st.dataframe(pd.DataFrame(_replicas), hide_index=True, use_container_width=True)
            st.markdown("**USGS forecast (first week):**")
            _pronostico = [
                {"Threshold": "M5.0+", "Estimated probability": "~100 % (near certain)", "Meaning": "Several expected"},
                {"Threshold": "M6.0+", "Estimated probability": "~40 %",                 "Meaning": "Possible, not certain"},
                {"Threshold": "M7.0+", "Estimated probability": "Very low",               "Meaning": "Extremely unlikely"},
            ]
            st.dataframe(pd.DataFrame(_pronostico), hide_index=True, use_container_width=True)
            st.info(
                "**The probability of a new earthquake of comparable magnitude (M7+) in the "
                "coming hours or days is extremely low.** The June 24 event was the most intense "
                "in Venezuela in **126 years** (since San Narciso, 1900). Seismologists note "
                "that with the energy accumulated over more than a century in the Boconó fault "
                "system now released, an immediate repeat has no physical basis. FUNVISIS and "
                "USGS monitor seismic activity continuously and in real time.\n\n"
                "🧭 **Follow post-earthquake safety precautions** — especially regarding damaged "
                "structures that may collapse during minor aftershocks."
            )
        else:
            st.markdown(
                "Tras el doble sismo del **24 jun 2026** se han registrado **más de 782 réplicas** "
                "(la mayor en M4.8). Son esperables y forman parte del proceso natural de "
                "estabilización cortical post-ruptura."
            )
            _replicas = [
                {"Fecha": "2026-jun-26", "Magnitud": "M4.7", "Zona": "La Guaira",
                 "Nota": "Colapso de puente en Caraballeda; daños adicionales en Caracas"},
                {"Fecha": "2026-jun-29", "Magnitud": "M4.6", "Zona": "Norte de Venezuela",
                 "Nota": "Sentida en Caracas y zona costera"},
                {"Fecha": "2026-jun-24 – 2026-jul-01",   "Magnitud": "≤M4.8", "Zona": "Región epicentral",
                 "Nota": "Más de 782 réplicas registradas; mayor en M4.8 (Asamblea Nacional, 1 jul)"},
            ]
            st.dataframe(pd.DataFrame(_replicas), hide_index=True, use_container_width=True)
            st.markdown("**Pronóstico USGS (primera semana):**")
            _pronostico = [
                {"Umbral": "M5.0+", "Probabilidad estimada": "~100 % (casi certeza)", "Significado": "Esperables varias"},
                {"Umbral": "M6.0+", "Probabilidad estimada": "~40 %",                 "Significado": "Posible, no segura"},
                {"Umbral": "M7.0+", "Probabilidad estimada": "Muy baja",              "Significado": "Extremadamente improbable"},
            ]
            st.dataframe(pd.DataFrame(_pronostico), hide_index=True, use_container_width=True)
            st.info(
                "**La probabilidad de un nuevo sismo de magnitud comparable (M7+) en las "
                "próximas horas o días es sumamente baja.** El evento del 24 de junio fue el "
                "más intenso en Venezuela en **126 años** (desde San Narciso, 1900). Los "
                "sismólogos señalan que, liberada la energía acumulada durante más de un siglo "
                "en el sistema de fallas de Boconó, una repetición inmediata carece de base "
                "física. FUNVISIS y el USGS monitorean la actividad de forma continua y en "
                "tiempo real.\n\n"
                "🧭 **Sigue las precauciones post-terremoto** — especialmente respecto a "
                "estructuras dañadas que pueden colapsar con réplicas menores."
            )
        _src_lbl = "Sources" if lang == "en" else "Fuentes"
        st.caption(
            f"{_src_lbl}: "
            "[USGS · Miyamoto International](https://miyamotointernational.com/venezuelas-strongest-earthquake-in-125-years-what-happened-on-june-24-2026/) · "
            "[Wikipedia EN](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
            "[SkyAlert MX](https://skyalert.mx/articulos/actualizacion-sismos-venezuela-2026) · "
            "[Ecoosfera](https://ecoosfera.com/noticias/sismos-venezuela-2026-teoria-placas/) · "
            "[Univision (29 jun)](https://www.univision.com/noticias/america-latina/ultimas-noticias-del-terremoto-en-venezuela-un-nuevo-sismo-de-4-2-vuelve-a-impactar-la-zona-norte-de-venezuela-en-medio-de-la-busqueda-de-mas-de-50-000-personas-atrapadas-hoy-29-de-junio-de-2026) · "
            "[El Tiempo (1 jul)](https://www.eltiempo.com/mundo/venezuela/venezuela-hoy-1-de-julio-tras-terremotos-organizaciones-de-venezolanos-en-estados-unidos-denuncian-obstaculos-a-la-llegada-y-distribucion-de-ayuda-3568145)"
        )
        st.page_link("pages/8_Replicas_en_vivo.py",
                     label="🌎 " + ("Live aftershocks — chart + map →" if lang == "en"
                                    else "Réplicas en vivo — gráfico + mapa →"))
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
            c2 = st.columns(2)
            c2[0].metric(t("magnitud", lang), f"M{a.get('magnitud')}")
            c2[1].metric(t("profundidad", lang), _km(a.get("profundidad_km")))
            _epicentro_linea(a)

    # ── DAÑOS POR SATÉLITE (NASA / Copernicus) ────────────────────────────────
    with st.expander(t("expander_nasa_danos", lang), expanded=False):
        if lang == "en":
            st.markdown(
                "Sentinel-1 SAR analysis (NASA) shows **>50 % of buildings** "
                "in Caraballeda, Macuto, La Guaira and Catia la Mar with a "
                "**≥ 75 % damage probability**. Copernicus EMS EMSR884 provides "
                "complementary damage cartography."
            )
            st.page_link(
                "pages/6_Mapa_NASA.py",
                label="Open interactive satellite damage map →",
                icon="🛰️",
            )
        else:
            st.markdown(
                "El análisis Sentinel-1 SAR (NASA) indica que **más del 50 % de los edificios** "
                "en Caraballeda, Macuto, La Guaira y Catia la Mar tienen "
                "**probabilidad de daño ≥ 75 %**. Copernicus EMS EMSR884 aporta "
                "cartografía complementaria de daño."
            )
            st.page_link(
                "pages/6_Mapa_NASA.py",
                label="Abrir mapa interactivo de daños por satélite →",
                icon="🛰️",
            )

    # ── RESPUESTA INTERNACIONAL ───────────────────────────────────────────────
    with st.expander(t("expander_respuesta_intl", lang), expanded=False):
        rc = st.columns(4)
        _paises_lbl    = "🌐 Countries"     if lang == "en" else "🌐 Países"
        _equipos_lbl   = "🔍 USAR Teams"    if lang == "en" else "🔍 Equipos USAR"
        _rescatist_lbl = "🧑‍🚒 Rescue Workers" if lang == "en" else "🧑‍🚒 Rescatistas"
        _perros_lbl    = "🐕 Dogs"           if lang == "en" else "🐕 Perros"
        rc[0].metric(_paises_lbl,    "27")
        rc[1].metric(_equipos_lbl,   "44")
        rc[2].metric(_rescatist_lbl, "3,660" if lang == "en" else "3.660")
        rc[3].metric(_perros_lbl,    "148")
        _na = "n/a" if lang == "en" else "s/d"
        if lang == "en":
            st.warning(
                "⚠️ **The official total (3,660 foreign rescue workers · 148 dogs) is the consolidated "
                "figure reported by Jorge Rodríguez on 1 Jul 2026** (plus 26,121 Venezuelan personnel "
                "and 15,467 registered volunteers). Individual "
                "country figures below are those published separately on 28 Jun — most have not released "
                "detailed breakdowns, which is why the table sum is lower than the official total."
            )
            _col_pais = "Country"
            _col_resc = "🧑‍🚒 Rescue Workers"
            _col_perr = "🐕 Dogs"
            _otros    = "Other 13 countries ✝"
        else:
            st.warning(
                "⚠️ **El total oficial (3.660 rescatistas extranjeros · 148 perros) es el dato "
                "consolidado reportado por Jorge Rodríguez el 1 jul 2026** (más 26.121 efectivos "
                "venezolanos y 15.467 voluntarios registrados). Las cifras por país son las "
                "publicadas individualmente el 28 jun — la mayoría no ha dado un desglose detallado, "
                "por eso la suma de la tabla es menor que el total oficial."
            )
            _col_pais = "País"
            _col_resc = "🧑‍🚒 Rescatistas"
            _col_perr = "🐕 Perros"
            _otros    = "Otros 13 países ✝"
        _rescate_rows = [
            {_col_pais: "El Salvador",   _col_resc: "300", _col_perr: "—"},
            {_col_pais: "United States" if lang == "en" else "Estados Unidos",
                                         _col_resc: "151", _col_perr: "12"},
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
            {_col_pais: "India",         _col_resc: "41",  _col_perr: "—"},
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
                "US: VA-TF1 (80p·6🐕) + LA County (71p·6🐕) · "
                "n/a = no figure published · "
                "Total workers & dogs: [J. Rodríguez 1 Jul](https://www.eltiempo.com/mundo/venezuela/venezuela-hoy-1-de-julio-tras-terremotos-organizaciones-de-venezolanos-en-estados-unidos-denuncian-obstaculos-a-la-llegada-y-distribucion-de-ayuda-3568145) · "
                "countries & teams: [OCHA 27 Jun](https://news.un.org/en/story/2026/06/1167825) · "
                "[State Dept.](https://www.state.gov/responding-to-venezuela-earthquakes) · "
                "[Wikipedia](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes)"
            )
        else:
            st.caption(
                "✝ Argentina, Canadá, Colombia, Ecuador, Guatemala, México, Panamá, Perú, "
                "Alemania, Rep. Checa, Jordania, Lituania, Qatar · "
                "EE.UU.: VA-TF1 (80p·6🐕) + Condado LA (71p·6🐕) · "
                "s/d = sin dato publicado · "
                "Total rescatistas y perros: [J. Rodríguez 1 jul](https://www.eltiempo.com/mundo/venezuela/venezuela-hoy-1-de-julio-tras-terremotos-organizaciones-de-venezolanos-en-estados-unidos-denuncian-obstaculos-a-la-llegada-y-distribucion-de-ayuda-3568145) · "
                "países y equipos: [OCHA 27 jun](https://news.un.org/en/story/2026/06/1167825) · "
                "[Depto. de Estado](https://www.state.gov/responding-to-venezuela-earthquakes) · "
                "[Wikipedia](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes)"
            )

    # ── AYUDA FINANCIERA INTERNACIONAL ───────────────────────────────────────
    with st.expander(t("expander_ayuda_financiera", lang), expanded=False):
        if lang == "en":
            st.markdown("Financial commitments from governments and international organizations (as of 30 Jun 2026):")
            _fin_rows = [
                {"Country / Organization": "🇺🇸 United States",     "Amount": ">$300 M",          "Channel": "USAID / OCHA / WFP / partners"},
                {"Country / Organization": "🇨🇳 China",              "Amount": "$14.7 M (¥100 M)", "Channel": "Government + Red Cross China"},
                {"Country / Organization": "🇪🇺 European Union",     "Amount": "€5 M (~$5.7 M)",   "Channel": "EU ECHO humanitarian aid"},
                {"Country / Organization": "🇰🇷 South Korea",        "Amount": "$5 M",              "Channel": "International organizations"},
                {"Country / Organization": "🇨🇦 Canada",             "Amount": "$5 M",              "Channel": "Humanitarian aid"},
                {"Country / Organization": "🏳 IFRC",                "Amount": "$2.5 M",            "Channel": "Red Cross Emergency Fund"},
                {"Country / Organization": "🇳🇱 Netherlands",        "Amount": "€2 M (~$2.3 M)",   "Channel": "Humanitarian operations"},
                {"Country / Organization": "🇪🇸 Spain",              "Amount": "€1 M (~$1.1 M)",   "Channel": "Emergency aid"},
                {"Country / Organization": "🕊 Vatican",             "Amount": "€100 K (~$114 K)",  "Channel": "Catholic aid structures in Venezuela"},
                {"Country / Organization": "🇷🇺 Russia",             "Amount": "not announced",      "Channel": "Humanitarian aid (announced)"},
                {"Country / Organization": "🏢 GEM + Walmart (US)", "Amount": "In-kind",            "Channel": "Supply logistics via USAID / State Dept."},
            ]
            st.markdown(f'<p class="swipe-hint">{t("swipe_hint", lang)}</p>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(_fin_rows), hide_index=True, use_container_width=True)
            st.caption(
                "⚠️ Figures reflect announced pledges; disbursements may differ. "
                "Sources: [State Dept.](https://www.state.gov/responding-to-venezuela-earthquakes) · "
                "[Al Jazeera](https://www.aljazeera.com/news/2026/6/26/which-countries-have-pledged-aid-to-venezuela-after-powerful-earthquakes) · "
                "[EU ECHO](https://civil-protection-humanitarian-aid.ec.europa.eu/news-stories/news/eu-delivers-emergency-aid-and-organises-humanitarian-flight-response-earthquakes-venezuela-2026-06-29_en) · "
                "[Korea Herald](https://www.koreaherald.com/article/10789913) · 30 Jun 2026"
            )
        else:
            st.markdown("Compromisos financieros de gobiernos y organismos internacionales (al 30 jun 2026):")
            _fin_rows = [
                {"País / Organismo": "🇺🇸 Estados Unidos",        "Monto": ">$300 M",           "Canal": "USAID / OCHA / WFP / socios"},
                {"País / Organismo": "🇨🇳 China",                  "Monto": "$14,7 M (¥100 M)", "Canal": "Gob. + Cruz Roja China"},
                {"País / Organismo": "🇪🇺 Unión Europea",         "Monto": "€5 M (~$5,7 M)",   "Canal": "EU ECHO ayuda humanitaria"},
                {"País / Organismo": "🇰🇷 Corea del Sur",         "Monto": "$5 M",              "Canal": "Organizaciones internacionales"},
                {"País / Organismo": "🇨🇦 Canadá",                "Monto": "$5 M",              "Canal": "Ayuda humanitaria"},
                {"País / Organismo": "🏳 FICR",                    "Monto": "$2,5 M",            "Canal": "Fondo emergencias Cruz Roja"},
                {"País / Organismo": "🇳🇱 Países Bajos",          "Monto": "€2 M (~$2,3 M)",   "Canal": "Operaciones humanitarias"},
                {"País / Organismo": "🇪🇸 España",                "Monto": "€1 M (~$1,1 M)",   "Canal": "Ayuda de emergencia"},
                {"País / Organismo": "🕊 Vaticano",                "Monto": "€100 K (~$114 K)", "Canal": "Estructuras eclesiásticas en VZ"},
                {"País / Organismo": "🇷🇺 Rusia",                 "Monto": "s/d",               "Canal": "Ayuda humanitaria (anunciado)"},
                {"País / Organismo": "🏢 GEM + Walmart (EE.UU.)", "Monto": "En especie",        "Canal": "Logística de suministros vía USAID / Depto. Estado"},
            ]
            st.markdown(f'<p class="swipe-hint">{t("swipe_hint", lang)}</p>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(_fin_rows), hide_index=True, use_container_width=True)
            st.caption(
                "⚠️ Cifras corresponden a compromisos anunciados; los desembolsos pueden diferir. "
                "Fuentes: [Depto. de Estado](https://www.state.gov/responding-to-venezuela-earthquakes) · "
                "[Al Jazeera](https://www.aljazeera.com/news/2026/6/26/which-countries-have-pledged-aid-to-venezuela-after-powerful-earthquakes) · "
                "[EU ECHO](https://civil-protection-humanitarian-aid.ec.europa.eu/news-stories/news/eu-delivers-emergency-aid-and-organises-humanitarian-flight-response-earthquakes-venezuela-2026-06-29_en) · "
                "[Korea Herald](https://www.koreaherald.com/article/10789913) · 30 jun 2026"
            )

    # ── OTRAS ZONAS Y CONTEXTO HUMANITARIO ────────────────────────────────────
    # Informativo, sin mapas propios: solo enlaces a fuentes multilaterales
    # neutrales (Wikipedia, OCHA, PAHO/OMS, ACNUR, OIM). Se evita deliberadamente
    # cualquier encuadre político; el foco son cifras humanitarias verificables.
    with st.expander(t("expander_otras_zonas", lang), expanded=False):
        if lang == "en":
            st.markdown("**Other states hit by the earthquake (not covered by this app's zone maps):**")
            st.markdown(
                "- 🏔️ **Yaracuy** (epicenter): ~3.9 M people exposed to severe shaking; "
                "damage reported in San Felipe, Cocorote and Independencia.\n"
                "- 🏗️ **Carabobo**: 14 dead, 67 injured (Naguanagua, Juan José Mora, Puerto Cabello, "
                "San Diego); over 25 homes destroyed in Morón and Urama from landslides and collapses.\n"
                "- 🏥 **Falcón**: 12 dead and 33 injured in the La Mar Suites building collapse; "
                "32 people treated for injuries overall."
            )
            st.caption(
                "🔗 Sources: "
                "[Wikipedia EN — consolidated](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
                "[OCHA Situation Report No. 5, 28 Jun](https://www.unocha.org/publications/report/venezuela-bolivarian-republic/earthquakes-venezuela-situation-report-no-5-28-june-2026-time-500-pm) · "
                "[PAHO/WHO Situation Report No. 1](https://www.paho.org/en/documents/situation-report-no1-earthquakes-venezuela-m72-and-m75)"
            )
            st.divider()
            st.markdown("**Separate emergency: flooding in Portuguesa state (independent of the earthquake):**")
            st.markdown(
                "Heavy rains caused the Chabasquén and Chabasquencito rivers and several streams to overflow "
                "in Portuguesa state on **28 Jun 2026**, flooding streets and homes in Chabasquén and affecting "
                "over 100 families. A bridge on the Troncal 007 highway partially collapsed, cutting off more "
                "than 20 sectors. Forecasts pointed to continued rain and flood risk in western and southern "
                "Venezuela into July."
            )
            st.caption(
                "🔗 Sources: "
                "[El Tiempo (Colombia), 28 Jun](https://www.eltiempo.com/mundo/venezuela/nueva-emergencia-en-venezuela-fuertes-lluvias-e-inundaciones-aislan-poblaciones-en-el-estado-portuguesa-3567692) · "
                "[El Heraldo, 28 Jun](https://www.elheraldo.co/mundo/2026/06/28/lluvias-e-inundaciones-agravan-la-emergencia-en-venezuela-tras-los-devastadores-terremotos/) · "
                "[NOAA Climate Prediction Center — regional hazards outlook](https://www.cpc.ncep.noaa.gov/products/international/nsamerica/nsamerica_hazard.pdf)"
            )
        else:
            st.markdown("**Otros estados afectados por el sismo (no cubiertos por los mapas de esta app):**")
            st.markdown(
                "- 🏔️ **Yaracuy** (epicentro): ~3,9 M de personas expuestas a sacudimiento severo; "
                "daños reportados en San Felipe, Cocorote e Independencia.\n"
                "- 🏗️ **Carabobo**: 14 fallecidos, 67 heridos (Naguanagua, Juan José Mora, Puerto Cabello, "
                "San Diego); más de 25 viviendas destruidas en Morón y Urama por deslizamientos y colapsos.\n"
                "- 🏥 **Falcón**: 12 fallecidos y 33 heridos por el colapso del edificio La Mar Suites; "
                "32 personas atendidas por lesiones en total."
            )
            st.caption(
                "🔗 Fuentes: "
                "[Wikipedia EN — consolidado](https://en.wikipedia.org/wiki/2026_Venezuela_earthquakes) · "
                "[OCHA, Reporte de Situación N.º 5, 28 jun](https://www.unocha.org/publications/report/venezuela-bolivarian-republic/earthquakes-venezuela-situation-report-no-5-28-june-2026-time-500-pm) · "
                "[OPS/OMS, Reporte de Situación N.º 1](https://www.paho.org/en/documents/situation-report-no1-earthquakes-venezuela-m72-and-m75)"
            )
            st.divider()
            st.markdown("**Emergencia: inundaciones en el estado Portuguesa (independiente del sismo):**")
            st.markdown(
                "Fuertes lluvias provocaron el desbordamiento de los ríos Chabasquén y Chabasquencito y "
                "varias quebradas en el estado Portuguesa el **28 jun 2026**, inundando calles y viviendas "
                "en Chabasquén y afectando a más de 100 familias. Un puente de la Troncal 007 colapsó "
                "parcialmente, dejando incomunicados más de 20 sectores. Los pronósticos meteorológicos "
                "mantenían riesgo de más lluvias e inundaciones en el occidente y sur del país entrando julio."
            )
            st.caption(
                "🔗 Fuentes: "
                "[El Tiempo (Colombia), 28 jun](https://www.eltiempo.com/mundo/venezuela/nueva-emergencia-en-venezuela-fuertes-lluvias-e-inundaciones-aislan-poblaciones-en-el-estado-portuguesa-3567692) · "
                "[El Heraldo, 28 jun](https://www.elheraldo.co/mundo/2026/06/28/lluvias-e-inundaciones-agravan-la-emergencia-en-venezuela-tras-los-devastadores-terremotos/) · "
                "[NOAA Climate Prediction Center — pronóstico regional de riesgos](https://www.cpc.ncep.noaa.gov/products/international/nsamerica/nsamerica_hazard.pdf)"
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
    st.markdown(f'<p style="opacity:0.85;">{t("ayuda_zona_nota", lang)}</p>',
                unsafe_allow_html=True)
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
            pob = fmt_int(row["pob"], lang) if pd.notna(row["pob"]) else "—"
            color = _color(row["mmi"])
            with col:
                # El color de intensidad va en el borde y el pin (señal no textual);
                # el nombre va en texto de alto contraste (WCAG AA) y las superficies
                # usan tokens de tema (legibles en claro y oscuro).
                st.markdown(f"""
<div style="border:1px solid var(--border-color,#e6dada);border-left:10px solid {color};
  border-radius:12px;padding:12px 14px 8px;
  background:var(--secondary-background-color,#f5f0ef);margin-bottom:4px;">
  <div style="font-size:1.2rem;font-weight:700;color:var(--text-color,#1a1a1a);">
    <span style="color:{color};">📍</span> {row['nombre']}</div>
  <div style="font-size:1.05rem;color:var(--text-color,#1a1a1a);opacity:0.92;">
    {t('kpi_mmi_max', lang)}: <span style="font-weight:800;font-size:1.15rem;">{mmi}</span>
    &nbsp;·&nbsp; {t('kpi_poblacion_residente', lang)}: <span style="font-weight:800;font-size:1.15rem;">{pob}</span></div>
</div>""", unsafe_allow_html=True)
                st.page_link(path, label="🆘 " + t("ver_ayuda_zona", lang))
    st.markdown(f'<p style="opacity:0.85;">{t("leyenda_zonas", lang)}</p>',
                unsafe_allow_html=True)
    st.page_link("pages/7_Asistente.py", label=t("ver_asistente", lang), icon="💬")
    st.image("assets/donar.png", use_container_width=True,
             caption=t("img_donar", lang))

    # ── CÓMO AYUDAR (donaciones) ──────────────────────────────────────────────
    if "centros_acopio_vzla" in cofu or "caritas_venezuela" in cofu:
        st.subheader("💚 " + t("ayudar_titulo", lang))
        if "centros_ayuda_vzla" in cofu:
            st.markdown(f"🔗 [{fuente_nombre(cofu['centros_ayuda_vzla'], lang)}]({cofu['centros_ayuda_vzla']['url']})")
        if "caritas_venezuela" in cofu:
            st.markdown(f"🔗 [{fuente_nombre(cofu['caritas_venezuela'], lang)}]({cofu['caritas_venezuela']['url']})")

    # ── RECURSOS PARA DAMNIFICADOS (página aparte) ────────────────────────────
    st.page_link("pages/9_Damnificados.py", label=t("ver_damnificados", lang), icon="🆘")

    # ── CONSEJOS POST-TERREMOTO (página aparte) ───────────────────────────────
    st.subheader("🧭 " + t("consejos_titulo", lang))
    st.page_link("pages/5_Consejos_post_terremoto.py", label="🧭 " + t("ver_consejos", lang))

    st.caption(f"🕒 {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")


# ── Navegación (la página principal se muestra como "Home") ───────────────────
pages = [
    st.Page(home, title="Home", icon="🏠", default=True),
    st.Page("pages/8_Replicas_en_vivo.py",         title="Réplicas en vivo / Live aftershocks", icon="🌎"),
    st.Page("pages/1_Caracas_Libertador.py",       title="Caracas — Libertador", icon="📍"),
    st.Page("pages/2_Caracas_Sucre_Petare.py",     title="Caracas — Sucre / Petare", icon="📍"),
    st.Page("pages/3_Caracas_Baruta_ElHatillo.py", title="Caracas — Baruta / Hatillo / Chacao", icon="📍"),
    st.Page("pages/4_La_Guaira_Litoral.py",        title="La Guaira — Litoral", icon="📍"),
    st.Page("pages/5_Consejos_post_terremoto.py",  title="Safety Tips / Consejos", icon="🧭"),
    st.Page("pages/6_Mapa_NASA.py",                title="NASA Satellite Map",       icon="🛰️"),
    st.Page("pages/7_Asistente.py",                title="Asistente / Assistant",    icon="💬"),
    st.Page("pages/9_Damnificados.py",             title="Ayuda Damnificados / Help",icon="🆘"),
]
st.navigation(pages).run()
