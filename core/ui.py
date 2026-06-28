"""Componentes de interfaz (Streamlit + Folium) — app informativa post-terremoto.

El mapa muestra INTENSIDAD SENTIDA (MMI) y recursos de ayuda. NO localiza
personas atrapadas ni modela probabilidad de sobrevivientes.
"""
import folium
import numpy as np
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

from core import scoring
from core.config import get_zone, load_config
from core.i18n import IDIOMAS, t
from core.pipeline import build_zone
from core.sources import fmt_vet_utc, parse_iso
from core.zunami import running_indicator_css

ALERT_COLORS = {"red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢"}


def _inject_responsive_css() -> None:
    st.markdown("""
<style>
/* ── MÓVIL (≤640px) ──────────────────────────────────────────────── */
@media (max-width: 640px) {

  /* Márgenes del contenedor principal */
  .block-container {
    padding: 0.6rem 0.6rem 2rem !important;
    max-width: 100% !important;
  }

  /* Columnas: 2 por fila (wrap) — mejor que apilar todo en 1 */
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.5rem 0.5rem !important;
  }
  [data-testid="column"] {
    min-width: 47% !important;
    flex: 1 1 47% !important;
  }

  /* Métricas: legibles y con fondo sutil */
  [data-testid="stMetric"] {
    background: rgba(0,0,0,0.04);
    border-radius: 8px;
    padding: 0.45rem 0.6rem !important;
  }
  [data-testid="stMetricLabel"] > div {
    font-size: 0.72rem !important;
    line-height: 1.2 !important;
  }
  [data-testid="stMetricValue"] > div {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
  }

  /* Page links: full-width, área de toque 48px */
  [data-testid="stPageLink"] {
    width: 100% !important;
  }
  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] button {
    width: 100% !important;
    min-height: 48px !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 0.8rem !important;
    display: flex !important;
    align-items: center !important;
  }

  /* Botones: full-width, táctiles */
  .stButton > button {
    width: 100% !important;
    min-height: 48px !important;
    font-size: 0.9rem !important;
  }

  /* Alertas: compactas */
  [data-testid="stAlert"] {
    font-size: 0.82rem !important;
    padding: 0.5rem 0.7rem !important;
    line-height: 1.4 !important;
  }

  /* Mapa: altura cómoda en móvil */
  iframe[title="streamlit_folium.st_folium"],
  .leaflet-container {
    height: 300px !important;
    min-height: 300px !important;
  }

  /* Dataframe: scroll horizontal sin desborde */
  [data-testid="stDataFrame"] {
    overflow-x: auto !important;
    font-size: 0.75rem !important;
  }

  /* Títulos ajustados */
  h1 { font-size: 1.35rem !important; line-height: 1.25 !important; }
  h2 { font-size: 1.1rem !important; }
  h3 { font-size: 0.95rem !important; }

  /* Captions y textos pequeños */
  .stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.72rem !important;
  }

  /* Progress bars */
  .stProgress > div > div > div {
    height: 10px !important;
    border-radius: 5px !important;
  }

  /* Sidebar */
  [data-testid="stSidebar"] { font-size: 0.88rem !important; }
  [data-testid="stSidebar"] button { min-height: 44px !important; }

  /* Ocultar header de tabla de zonas en móvil (ya no tiene sentido con cards) */
  .zona-table-header { display: none !important; }
}

/* ── TABLET (641px – 1024px) ─────────────────────────────────────── */
@media (min-width: 641px) and (max-width: 1024px) {

  .block-container {
    padding: 1rem 1.2rem 2rem !important;
    max-width: 100% !important;
  }

  /* Columnas de 4: 2×2 */
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.4rem !important;
  }
  [data-testid="column"] {
    min-width: 46% !important;
    flex: 1 1 46% !important;
  }

  [data-testid="stMetricValue"] > div { font-size: 1.2rem !important; }

  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] button {
    min-height: 44px !important;
    font-size: 0.92rem !important;
  }

  iframe[title="streamlit_folium.st_folium"] {
    height: 400px !important;
  }

  h1 { font-size: 1.55rem !important; }
}

/* ── MEJORAS GENERALES (todos los tamaños) ───────────────────────── */

/* Progress bars suaves */
.stProgress > div > div > div {
  border-radius: 4px !important;
  transition: width 0.6s ease !important;
}

/* Page links: hover suave rojo-rescate */
[data-testid="stPageLink"] a {
  border-radius: 8px !important;
  transition: background 0.15s, transform 0.1s !important;
}
[data-testid="stPageLink"] a:hover {
  background: rgba(183,28,28,0.08) !important;
  transform: translateX(2px) !important;
}

/* Zona cards: separación visual entre zonas */
.zona-card {
  border-left: 3px solid #b71c1c;
  padding-left: 0.5rem;
  margin-bottom: 0.25rem;
}

/* En móvil: cards de zona a ancho completo (override del 47% genérico) */
@media (max-width: 640px) {
  /* El grid 2x2 de mapas va a 1 columna en móvil */
  [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) [data-testid="column"] {
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }
}

/* Botón "Abrir mapa" — estilo prominente en todos los tamaños */
[data-testid="stPageLink"] a {
  background: rgba(183,28,28,0.06) !important;
  border: 1.5px solid rgba(183,28,28,0.3) !important;
  border-radius: 8px !important;
  padding: 0.55rem 1rem !important;
  font-weight: 600 !important;
  color: #b71c1c !important;
  transition: background 0.15s, border-color 0.15s, transform 0.1s !important;
  display: inline-flex !important;
  align-items: center !important;
  min-height: 44px !important;
  width: 100% !important;
  justify-content: center !important;
}
[data-testid="stPageLink"] a:hover {
  background: rgba(183,28,28,0.14) !important;
  border-color: #b71c1c !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 2px 8px rgba(183,28,28,0.18) !important;
}
</style>
""", unsafe_allow_html=True)
    # Zunami: ciclo propio de figuras (corriendo, silla de ruedas, bici, nado, remo)
    # + perro, sustituyendo el indicador nativo (sin el "hombre estático").
    st.markdown(f"<style>{running_indicator_css()}</style>", unsafe_allow_html=True)


def _render_construction_banner(lang: str) -> None:
    if lang == "en":
        msg = ("ℹ️ Information app. Real, attributed data (USGS, OSM, GDACS). "
               "Emergencies: call **171** or **911**.")
    else:
        msg = ("ℹ️ App informativa. Datos reales y atribuidos (USGS, OSM, GDACS). "
               "Emergencias: llama al **171** o **911**.")
    st.info(msg)


def apply_chrome(config: dict) -> str:
    """Idioma, auto-refresco en tiempo real y botón de actualizar. Devuelve lang."""
    if "lang" not in st.session_state:
        st.session_state.lang = "es"
    _inject_responsive_css()
    secs = int(config.get("autorefresco_segundos", 0) or 0)
    if secs > 0:
        st_autorefresh(interval=secs * 1000, key="auto")
    codes = list(IDIOMAS.keys())
    _render_construction_banner(st.session_state.lang)
    lang = st.sidebar.selectbox(t("idioma", st.session_state.lang), codes,
                                index=codes.index(st.session_state.lang),
                                format_func=lambda c: IDIOMAS[c])
    st.session_state.lang = lang
    if st.sidebar.button(t("actualizar", lang)):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(f"🕒 {t('ultima_actualizacion', lang)}:\n\n{fmt_vet_utc()}")
    return lang


def _status_icon(status: str) -> str:
    return {"ok": "🟢", "no_disponible": "🔴", "proyeccion": "🔵"}.get(status, "⚪")


def render_sources(ctx: dict, lang: str) -> None:
    """Procedencia: cada capa con estado, enlace oficial y hora de obtención."""
    f = ctx.get("fuentes", {})
    with st.sidebar.expander("📚 " + t("fuentes_titulo", lang), expanded=False):
        for ly in ctx.get("layers", []):
            estado = (t("estado_ok", lang) if ly["status"] == "ok"
                      else t("proyeccion_estadistica", lang) if ly["status"] == "proyeccion"
                      else t("no_disponible", lang))
            st.markdown(f"{_status_icon(ly['status'])} **{ly['nombre']}** — {estado}  \n"
                        f"[{t('ver_fuente', lang)}]({ly['url']})"
                        + (f"  \n_{ly['fetched']}_" if ly.get("fetched") else "")
                        + (f"  \n_{ly['detalle']}_" if ly.get("detalle") else ""))

        st.markdown("---")
        for key in ("usgs_evento", "usgs_evento_secundario", "usgs_pager",
                    "usgs_ground_failure", "gdacs", "reliefweb", "copernicus_emsr884",
                    "unosat", "maxar_open_data", "icrc_rfl", "cruz_roja_venezolana",
                    "proteccion_civil", "worldpop", "osm"):
            if key in f:
                st.markdown(f"🔗 [{f[key]['nombre']}]({f[key]['url']})")
    st.sidebar.caption(t("atribucion", lang))


def render_event_banner(ctx: dict, lang: str) -> None:
    """Qué pasó: evento real USGS, sismo doble, PAGER y tiempo transcurrido."""
    s = ctx["sismo"]
    hs = ctx["hours_since"]
    place = s.get("lugar", "")
    st.markdown(f"**{t('evento_real', lang)}:** M{s.get('magnitud')} · {place} · "
                f"{t('hora_evento', lang)}: {fmt_vet_utc(parse_iso(s['origen_iso']))}")

    adicionales = ctx.get("sismos_adicionales", [])
    n_sm = ctx.get("n_shakemaps", 1)
    if adicionales or n_sm > 1:
        a = adicionales[0] if adicionales else {}
        st.warning(t("sismo_doble_banner", lang,
                     m1=s.get("id", ""), mag1=s.get("magnitud", "?"),
                     m2=a.get("id", ""), mag2=a.get("magnitud", "?")))

    cols = st.columns(3)
    cols[0].metric(t("horas_transcurridas", lang), f"{hs:.0f} h")
    if ctx.get("mmi_max") is not None:
        cols[1].metric(t("kpi_mmi_max", lang), f"{ctx['mmi_max']:.1f}")
    if ctx.get("alert_pager"):
        cols[2].metric(t("pager_nivel", lang),
                       f"{ALERT_COLORS.get(ctx['alert_pager'], '')} {ctx['alert_pager'].upper()}")
    st.caption(t("actualizacion_tiempo_real", lang))


def _build_map(df, zone, ctx, lang):
    """Mapa de INTENSIDAD sentida (MMI) + recursos de ayuda."""
    lon_min, lat_min, lon_max, lat_max = zone["bbox"]
    m = folium.Map(location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2],
                   zoom_start=14, tiles="CartoDB positron", control_scale=True)
    if ctx["shakemap_ok"] and "mmi" in df.columns:
        heat = df.dropna(subset=["mmi"]).copy()
        # Índice de AFECTACIÓN probable: sacudimiento × población expuesta (+ realce
        # por fallo de terreno). La población es el discriminador real dentro de una
        # zona pequeña (la MMI apenas varía a esta escala). Así el rojo marca las
        # zonas más afectadas (a dónde ir a ayudar) y el mar/parques quedan fuera.
        liq = heat["liquefaccion"].values if "liquefaccion" in heat.columns else None
        desl = heat["deslizamiento"].values if "deslizamiento" in heat.columns else None
        pop = heat["pop"].values if "pop" in heat.columns else np.ones(len(heat))
        heat["score"] = scoring.impact_exposure(heat["mmi"].values, pop, liq, desl)
        heat = heat[heat["score"] > 0]
        if not heat.empty:
            # Normalización robusta por percentiles (una celda atípica no aplana el resto).
            # sqrt suaviza el degradado para que las zonas intermedias se vean (no solo
            # los picos): rojo = más afectada → naranja/amarillo → frío = menos.
            s = heat["score"].values
            lo, hi = float(np.nanpercentile(s, 5)), float(np.nanpercentile(s, 99))
            heat["w"] = (np.sqrt(np.clip((s - lo) / (hi - lo), 0.0, 1.0))
                         if hi - lo > 1e-9 else 0.5)
            HeatMap(heat[["lat", "lon", "w"]].values.tolist(),
                    radius=18, blur=14, min_opacity=0.30).add_to(m)
            # Marcadores de las celdas MÁS afectadas (referencia para rescatistas)
            for _, r in heat.nlargest(12, "score").iterrows():
                maps_url = f"https://www.google.com/maps/search/?api=1&query={r['lat']},{r['lon']}"
                popup_html = (
                    f"{t('col_mmi', lang)}: {r['mmi']:.1f}"
                    + (f"<br>{t('col_area', lang)}: {r['area']}" if "area" in r else "")
                    + f'<br><a href="{maps_url}" target="_blank">📍 Google Maps</a>'
                )
                folium.CircleMarker(
                    [r["lat"], r["lon"]], radius=6, weight=1, color="#bd0026",
                    fill=True, fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=220)).add_to(m)
    # Recursos de ayuda (OSM): dónde acudir — siempre visibles
    for _, r in ctx["resources"].iterrows():
        maps_url = f"https://www.google.com/maps/search/?api=1&query={r['lat']},{r['lon']}"
        popup_html = (
            f"<b>{r['etiqueta']}</b>: {r['nombre']}"
            f'<br><a href="{maps_url}" target="_blank">📍 Google Maps</a>'
        )
        folium.Marker(
            [r["lat"], r["lon"]],
            icon=folium.Icon(color="green" if r["tipo"] in ("hospital", "clinic") else
                             "red" if r["tipo"] == "fire_station" else "blue",
                             icon="plus" if r["tipo"] in ("hospital", "clinic") else "info-sign"),
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(m)
    return m


def render_zone(zone_id: str) -> None:
    config = load_config()
    lang = apply_chrome(config)
    zone = get_zone(config, zone_id)
    df, ctx = _cached_zone(zone_id, config.get("autorefresco_segundos", 0))
    render_sources(ctx, lang)

    st.title(zone["nombre"])
    st.caption(t("subtitulo_zona", lang))
    if not ctx["shakemap_ok"]:
        st.error(t("banner_sin_shakemap", lang))

    # ── MAPA: intensidad sentida + recursos de ayuda ──────────────────────────
    st_folium(_build_map(df, zone, ctx, lang), height=480, width="stretch",
              returned_objects=[], key=f"map_{zone_id}")
    st.caption(t("leyenda_intensidad", lang))

    # ── KPIs informativos ─────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric(t("kpi_mmi_max", lang), f"{ctx['mmi_max']:.1f}" if ctx.get("mmi_max") else "—")
    c2.metric(t("kpi_poblacion_residente", lang),
              f"{ctx['poblacion_total']:,}" if ctx.get("poblacion_total") else "—")
    c3.metric(t("recursos_titulo", lang), f"{len(ctx['resources'])}")

    # ── Peligro ground-failure (si hay datos por celda) ───────────────────────
    if ctx.get("gf_cell") and ctx.get("areas"):
        liq = max((a.get("liquefaccion_max", 0) or 0) for a in ctx["areas"])
        des = max((a.get("deslizamiento_max", 0) or 0) for a in ctx["areas"])
        if liq > 0 or des > 0:
            st.caption(t("peligro_gf", lang, liq=f"{liq*100:.0f}", des=f"{des*100:.0f}"))

    # ── RECURSOS DE AYUDA por área (pieza central) ────────────────────────────
    st.subheader("🆘 " + t("ayuda_titulo", lang))
    if not ctx["resources"].empty:
        res = ctx["resources"]
        has_area = "area" in res.columns
        titulo = f"🏥 {t('recursos_titulo', lang)} ({len(res)})"
        with st.expander(titulo, expanded=True):
            if has_area:
                areas = sorted(res["area"].unique())
            else:
                areas = [None]

            for area in areas:
                group = res[res["area"] == area] if has_area and area else res
                if group.empty:
                    continue
                if has_area and area:
                    st.markdown(f"#### 📌 {area}")

                for _, r in group.sort_values("tipo").iterrows():
                    tel      = r.get("telefono", "") or ""
                    addr     = r.get("direccion", "") or ""
                    web      = r.get("web", "") or ""
                    maps_url = (f"https://www.google.com/maps/search/?api=1"
                                f"&query={r['lat']},{r['lon']}")

                    tel_line  = f"📞 [{tel}](tel:{tel.replace(' ','')})" if tel else ""
                    addr_line = f"📍 {addr}" if addr else ""
                    web_line  = f"🌐 [{web}]({web})" if web else ""
                    detail    = "  \n".join(x for x in [tel_line, addr_line, web_line] if x)
                    detail   += ("  \n" if detail else "") + f"[📍 Ver en mapa]({maps_url})"

                    st.markdown(f"**{r['etiqueta']}** — {r['nombre']}  \n{detail}")
                    st.divider()
    else:
        st.info(t("recursos_ninguno", lang))

    # ── INTENSIDAD POR BARRIO (informativo, sin probabilidades) ───────────────
    if ctx.get("areas"):
        with st.expander("📊 " + t("intensidad_barrio_titulo", lang), expanded=False):
            rows = []
            for a in ctx["areas"]:
                row = {t("col_area", lang): a["area"],
                       t("col_mmi", lang): round(a["mmi_max"], 1),
                       t("kpi_poblacion_residente", lang): int(a["poblacion"])}
                if "liquefaccion_max" in a:
                    row[t("col_licuefaccion", lang)] = f"{a['liquefaccion_max']*100:.0f}%"
                if "deslizamiento_max" in a:
                    row[t("col_deslizamiento", lang)] = f"{a['deslizamiento_max']*100:.0f}%"
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption(t("intensidad_barrio_nota", lang))

    # ── SEGURIDAD Y FUENTES OFICIALES ─────────────────────────────────────────
    _render_official_links(ctx["fuentes"], lang)

    # ── QUÉ PASÓ (evento) ─────────────────────────────────────────────────────
    with st.expander("📍 " + t("sismo_titulo", lang), expanded=False):
        render_event_banner(ctx, lang)

    st.caption(f"🕒 {t('ultima_actualizacion', lang)}: {ctx['updated_at']}")


def _render_official_links(f: dict, lang: str) -> None:
    """Tarjeta de seguridad: emergencias + mapas de daño oficiales."""
    st.subheader("🛟 " + t("seguridad_titulo", lang))
    links = []
    for key in ("proteccion_civil", "copernicus_emsr884", "unosat",
                "reliefweb", "gdacs", "icrc_rfl", "cruz_roja_venezolana"):
        if key in f:
            links.append(f"🔗 [{f[key]['nombre']}]({f[key]['url']})")
    st.markdown("  \n".join(links))


@st.cache_data(ttl=300, show_spinner=False)
def _cached_zone(zone_id: str, _refresh_salt: int):
    config = load_config()
    return build_zone(get_zone(config, zone_id), config)
