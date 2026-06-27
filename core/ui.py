"""Componentes de interfaz reutilizables (Streamlit + Folium).

Framing: el mapa muestra PROBABILIDAD DE SOBREVIVIENTES CON VIDA, no víctimas.
"""
import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

from core.config import get_zone, load_config
from core.i18n import IDIOMAS, t
from core.pipeline import build_zone
from core.sources import fmt_vet_utc, parse_iso

PRIORITY_COLORS = {"alta": "#b30000", "media": "#f4a300", "baja": "#2c7fb8", "—": "#999"}
RESOURCE_COLORS = {"hospital": "#1a9850", "clinic": "#66bd63", "fire_station": "#d73027",
                   "ambulance_station": "#fc8d59", "shelter": "#4575b4"}
ALERT_COLORS = {"red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢"}


def _inject_responsive_css() -> None:
    st.markdown("""
<style>
/* ── MÓVIL (≤640px) ──────────────────────────────────────────────── */
@media (max-width: 640px) {

  /* Márgenes del contenedor principal */
  .block-container {
    padding: 0.75rem 0.75rem 2rem !important;
    max-width: 100% !important;
  }

  /* Columnas: apilar verticalmente */
  [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
    gap: 0.4rem !important;
  }
  [data-testid="column"] {
    width: 100% !important;
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }

  /* Métricas: más grandes y fáciles de tocar */
  [data-testid="stMetric"] {
    background: rgba(0,0,0,0.04);
    border-radius: 8px;
    padding: 0.5rem 0.75rem !important;
  }
  [data-testid="stMetricLabel"] > div {
    font-size: 0.78rem !important;
  }
  [data-testid="stMetricValue"] > div {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
  }

  /* Botones y page_links: full width, tacto fácil */
  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] button {
    width: 100% !important;
    min-height: 48px !important;
    font-size: 1rem !important;
    padding: 0.6rem 1rem !important;
  }
  .stButton > button {
    width: 100% !important;
    min-height: 48px !important;
    font-size: 0.95rem !important;
  }

  /* Alertas/banners: texto más compacto */
  [data-testid="stAlert"] {
    font-size: 0.85rem !important;
    padding: 0.6rem 0.8rem !important;
  }

  /* Mapa: altura reducida para no dominar la pantalla */
  iframe[title="streamlit_folium.st_folium"] {
    height: 320px !important;
  }

  /* Tabla dataframe: scroll horizontal sin desborde */
  [data-testid="stDataFrame"] {
    overflow-x: auto !important;
  }
  [data-testid="stDataFrame"] > div {
    font-size: 0.78rem !important;
  }

  /* Subheaders y títulos más ajustados */
  h1 { font-size: 1.4rem !important; }
  h2 { font-size: 1.15rem !important; }
  h3 { font-size: 1rem !important; }

  /* Progress bars: altura mínima legible */
  .stProgress > div > div > div {
    height: 10px !important;
    border-radius: 5px !important;
  }

  /* Sidebar: texto y controles más grandes al abrirlo */
  [data-testid="stSidebar"] {
    font-size: 0.9rem !important;
  }
  [data-testid="stSidebar"] button {
    min-height: 44px !important;
  }
}

/* ── TABLET (641px – 1024px) ─────────────────────────────────────── */
@media (min-width: 641px) and (max-width: 1024px) {

  .block-container {
    padding: 1rem 1.5rem 2rem !important;
    max-width: 100% !important;
  }

  /* Columnas de 4: reducir a 2 filas de 2 */
  [data-testid="column"] {
    min-width: 48% !important;
    flex: 1 1 48% !important;
  }

  [data-testid="stMetricValue"] > div {
    font-size: 1.25rem !important;
  }

  [data-testid="stPageLink"] a,
  [data-testid="stPageLink"] button {
    min-height: 44px !important;
    font-size: 0.95rem !important;
  }

  /* Mapa a altura razonable */
  iframe[title="streamlit_folium.st_folium"] {
    height: 420px !important;
  }

  h1 { font-size: 1.6rem !important; }
}

/* ── MEJORAS GENERALES (todos los tamaños) ───────────────────────── */

/* Barras de progreso más suaves */
.stProgress > div > div > div {
  border-radius: 4px !important;
  transition: width 0.5s ease !important;
}

/* Page links como tarjetas tocables */
[data-testid="stPageLink"] a {
  border-radius: 8px !important;
  transition: background 0.15s !important;
}
[data-testid="stPageLink"] a:hover {
  background: rgba(183,28,28,0.08) !important;
}
</style>
""", unsafe_allow_html=True)


def _render_construction_banner(lang: str) -> None:
    if lang == "en":
        msg = ("🚧 **Under construction** — Real data (USGS/OSM), still being validated. "
               "Complement with field information.")
    else:
        msg = ("🚧 **App en construcción** — Datos reales (USGS/OSM), aún en validación. "
               "Complementar con información de campo.")
    st.warning(msg)


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
                    "usgs_ground_failure", "copernicus_ems", "maxar_open_data",
                    "unosat", "nasa_aria", "meta_hrsl", "hot",
                    "hazus", "pager_inventory"):
            if key in f:
                st.markdown(f"🔗 [{f[key]['nombre']}]({f[key]['url']})")
    st.sidebar.caption(t("atribucion", lang))


def render_event_banner(ctx: dict, lang: str) -> None:
    """Modo, sismo doble, reloj 72h, PAGER y peligros secundarios."""
    modo = ctx["modo"]
    (st.error if modo == "operativo" else st.warning)(
        t("modo_operativo_label" if modo == "operativo" else "modo_demo_label", lang))

    s = ctx["sismo"]
    hs = ctx["hours_since"]
    place = s.get("lugar", "")
    st.markdown(f"**{t('evento_real', lang)}:** M{s.get('magnitud')} · {place} · "
                f"{t('hora_evento', lang)}: {fmt_vet_utc(parse_iso(s['origen_iso']))}")

    # --- Sismo doble ---
    adicionales = ctx.get("sismos_adicionales", [])
    n_sm = ctx.get("n_shakemaps", 1)
    if adicionales or n_sm > 1:
        a = adicionales[0] if adicionales else {}
        mag1 = s.get("magnitud", "?")
        mag2 = a.get("magnitud", "?")
        st.warning(t("sismo_doble_banner", lang,
                     m1=s.get("id", ""), mag1=mag1,
                     m2=a.get("id", ""), mag2=mag2))
        st.caption(f"ShakeMaps combinados (MMI máx): {n_sm} eventos")

    # --- Actualización en tiempo real ---
    st.caption(t("actualizacion_tiempo_real", lang))

    V1, V2 = 72, 120
    if hs < V1:
        st.info(t("alerta_ventana72", lang))
    elif hs < V2:
        st.warning(t("ventana_secundaria_aviso", lang))
    else:
        st.warning(t("ventana_agotada", lang))

    cols = st.columns(4)
    cols[0].metric(t("horas_transcurridas", lang), f"{hs:.1f} h")
    cols[1].metric(t("horas_restantes", lang),
                   f"{max(V1 - hs, 0):.1f} h" if hs < V1
                   else f"{max(V2 - hs, 0):.1f} h " + ("(vent. secundaria)" if lang == "es" else "(sec.window)"))
    if ctx.get("alert_pager"):
        cols[2].metric(t("pager_nivel", lang),
                       f"{ALERT_COLORS.get(ctx['alert_pager'], '')} {ctx['alert_pager'].upper()}")
    gf = ctx.get("ground_failure") or {}
    if gf.get("liquefaction_pop"):
        cols[3].metric(t("exposicion_licuefaccion", lang),
                       f"{ALERT_COLORS.get(gf.get('liquefaction_alert'),'')} "
                       f"{int(gf['liquefaction_pop']):,}")


def _build_map(df, zone, ctx, lang):
    lon_min, lat_min, lon_max, lat_max = zone["bbox"]
    m = folium.Map(location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2],
                   zoom_start=14, tiles="CartoDB positron", control_scale=True)
    if ctx["shakemap_ok"]:
        HeatMap(df[["lat", "lon", "score_norm"]].dropna().values.tolist(),
                radius=18, blur=14, min_opacity=0.25).add_to(m)
        for _, r in df.nlargest(15, "score_norm").iterrows():
            pop_txt = "—" if pd.isna(r.get("pop")) else f"{int(r['pop'])}"
            folium.CircleMarker(
                [r["lat"], r["lon"]], radius=6, weight=1,
                color=PRIORITY_COLORS.get(r["prioridad"], "#b30000"),
                fill=True, fill_opacity=0.85,
                popup=folium.Popup(
                    f"<b>{r['cell_id']}</b><br>{t('col_mmi', lang)}: {r['mmi']:.1f}<br>"
                    f"{t('col_pob_celda', lang)}: {pop_txt}<br>"
                    f"{t('col_score', lang)}: {r['score_norm']:.2f}", max_width=220)
            ).add_to(m)
    # Recursos críticos (OSM) — siempre visibles
    for _, r in ctx["resources"].iterrows():
        folium.Marker(
            [r["lat"], r["lon"]],
            icon=folium.Icon(color="green" if r["tipo"] in ("hospital", "clinic") else
                             "red" if r["tipo"] == "fire_station" else "blue",
                             icon="plus" if r["tipo"] in ("hospital", "clinic") else "info-sign"),
            popup=f"{r['etiqueta']}: {r['nombre']}",
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
    render_event_banner(ctx, lang)

    # --- Banderas de disponibilidad ---
    if not ctx["shakemap_ok"]:
        st.error(t("banner_sin_shakemap", lang))
    if not ctx["pop_available"]:
        st.warning(t("banner_sin_poblacion", lang))
    elif ctx.get("pop_src") == "remota":
        st.info(t("banner_pop_remota", lang))
    if ctx.get("proyec_ok"):
        st.caption(t("nota_proyeccion", lang))

    n_alta = int((df["prioridad"] == "alta").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric(t("kpi_mmi_max", lang), f"{df['mmi'].max():.1f}" if ctx["shakemap_ok"] else "—")
    c2.metric(t("kpi_celdas_alta", lang), f"{n_alta}")
    c3.metric(t("recursos_titulo", lang), f"{len(ctx['resources'])}")

    st_folium(_build_map(df, zone, ctx, lang), height=520, width="stretch",
              returned_objects=[], key=f"map_{zone_id}")
    st.caption(f"{t('leyenda', lang)}: 🔴 {t('prioridad_alta', lang)} · "
               f"🟠 {t('prioridad_media', lang)} · 🔵 {t('prioridad_baja', lang)} — "
               f"{t('nota_modelo', lang)}")
    if ctx["pop_available"]:
        st.caption("ℹ️ " + t("nota_poblacion", lang))

    if ctx["shakemap_ok"]:
        st.subheader(t("tabla_prioridad", lang))
        top = df.nlargest(20, "score_norm").copy()
        top["prioridad"] = top["prioridad"].map(lambda k: t(f"prioridad_{k}", lang)
                                                 if k in ("alta", "media", "baja") else k)
        view_cols = ["cell_id", "lat", "lon", "mmi", "pop", "prioridad", "score_norm"]
        view_cols = [c for c in view_cols if c in top.columns]
        view = top[view_cols].rename(columns={
            "cell_id": t("col_celda", lang), "lat": t("col_lat", lang),
            "lon": t("col_lon", lang), "mmi": t("col_mmi", lang),
            "pop": t("col_pob_celda", lang), "prioridad": t("col_prioridad", lang),
            "score_norm": t("col_score", lang)})
        st.dataframe(view, width="stretch", hide_index=True)
        st.download_button(t("descargar_csv", lang), df.to_csv(index=False).encode("utf-8"),
                           file_name=f"prioridad_{zone_id}.csv", mime="text/csv")

    if not ctx["resources"].empty:
        with st.expander("🏥 " + t("recursos_titulo", lang)):
            st.dataframe(ctx["resources"][["etiqueta", "nombre", "lat", "lon"]],
                         width="stretch", hide_index=True)


@st.cache_data(ttl=110, show_spinner=False)
def _cached_zone(zone_id: str, _refresh_salt: int):
    config = load_config()
    return build_zone(get_zone(config, zone_id), config)
