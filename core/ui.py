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
    """Sismo doble, reloj ventanas, PAGER y peligros secundarios."""
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

    # ── TÍTULO + modo + alerta crítica (mínimo antes del mapa) ──────────────
    st.title(zone["nombre"])
    if ctx["modo"] == "operativo":
        st.success(t("modo_operativo_label", lang))
    else:
        st.warning(t("modo_demo_label", lang))
    if not ctx["shakemap_ok"]:
        st.error(t("banner_sin_shakemap", lang))

    # ── MAPA — primero, sin scroll ────────────────────────────────────────────
    st_folium(_build_map(df, zone, ctx, lang), height=520, width="stretch",
              returned_objects=[], key=f"map_{zone_id}")
    st.caption(f"{t('leyenda', lang)}: 🔴 {t('prioridad_alta', lang)} · "
               f"🟠 {t('prioridad_media', lang)} · 🔵 {t('prioridad_baja', lang)} — "
               f"{t('nota_modelo', lang)}")

    # ── KPIs compactos justo debajo del mapa ─────────────────────────────────
    n_alta = int((df["prioridad"] == "alta").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric(t("kpi_mmi_max", lang), f"{df['mmi'].max():.1f}" if ctx["shakemap_ok"] else "—")
    c2.metric(t("kpi_celdas_alta", lang), f"{n_alta}")
    c3.metric(t("recursos_titulo", lang), f"{len(ctx['resources'])}")

    st.markdown("---")

    # ── BANNER DE EVENTO (plegado por defecto, accesible) ────────────────────
    with st.expander("📍 " + t("sismo_titulo", lang) + " · ⏳ " + t("reloj_titulo", lang),
                     expanded=False):
        render_event_banner(ctx, lang)

    # ── DISPONIBILIDAD Y PROYECCIONES ─────────────────────────────────────────
    pop_src = ctx.get("pop_src", "no_disponible")
    _POP_SRC_MSG = {
        "local":      ("banner_pop_remota", "info"),   # reutiliza texto similar
        "remota":     ("banner_pop_remota", "info"),
        "api":        ("banner_pop_api",    "info"),
        "censo_ine":  ("banner_pop_censo",  "info"),
    }
    if not ctx["pop_available"]:
        st.warning(t("banner_sin_poblacion", lang))
    elif pop_src in _POP_SRC_MSG:
        key, lvl = _POP_SRC_MSG[pop_src]
        getattr(st, lvl)(t(key, lang))
    if ctx.get("proyec_ok"):
        st.caption(t("nota_proyeccion", lang))

    # ── TABLA DE PRIORIDAD — solo celdas con esperanza (p_vida > 0) ───────────
    if ctx["shakemap_ok"]:
        st.subheader(t("tabla_prioridad", lang))

        # Solo lugares donde aún hay probabilidad de hallar sobrevivientes con vida.
        con_esperanza = df[df["p_vida"] > 0].copy() if "p_vida" in df.columns else df.copy()

        if con_esperanza.empty:
            # No hay celdas con probabilidad > 0 en esta zona
            st.info(
                "🔍 En esta zona, el modelo no identifica celdas con probabilidad "
                "de supervivencia mayor que cero en este momento. Esto **no descarta "
                "sobrevivientes**: mantener la búsqueda guiada por reportes de campo "
                "confirmados y reevaluar con cada actualización."
                if lang == "es" else
                "🔍 In this zone, the model finds no cells with survival probability "
                "above zero right now. This does **not rule out survivors**: keep "
                "search guided by confirmed field reports and reassess on each update."
            )
        else:
            top = con_esperanza.nlargest(20, "p_vida")
            n_total = len(con_esperanza)
            top = top.copy()
            top["prioridad"] = top["prioridad"].map(
                lambda k: t(f"prioridad_{k}", lang) if k in ("alta", "media", "baja") else k)
            # p_vida → porcentaje legible (probabilidad absoluta de hallar con vida)
            top["p_vida_pct"] = top["p_vida"].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—")
            # Personas estimadas presentes al momento del sismo
            if "pop" in top.columns:
                top["pop"] = top["pop"].apply(
                    lambda x: f"~{int(x):,}" if pd.notna(x) and x is not None else "—")

            pop_src = ctx.get("pop_src", "")
            src_suffix = {"censo_ine": " (INE)", "api": " (WorldPop API)",
                          "local": " (WorldPop)", "remota": " (WorldPop)"}.get(pop_src, "")
            col_pop = (f"Personas en celda{src_suffix}" if lang == "es"
                       else f"Persons in cell{src_suffix}")
            col_prob = ("Prob. hallar con vida" if lang == "es" else "Prob. find alive")

            view_cols = ["cell_id", "lat", "lon", "mmi", "pop", "prioridad", "p_vida_pct"]
            view_cols = [c for c in view_cols if c in top.columns]
            view = top[view_cols].rename(columns={
                "cell_id": t("col_celda", lang), "lat": t("col_lat", lang),
                "lon": t("col_lon", lang), "mmi": t("col_mmi", lang),
                "pop": col_pop, "prioridad": t("col_prioridad", lang),
                "p_vida_pct": col_prob})
            st.dataframe(view, width="stretch", hide_index=True)

            st.caption(
                f"✅ Mostrando las {len(top)} celdas con mayor probabilidad de hallar "
                f"sobrevivientes con vida ({n_total} celdas con esperanza en la zona)."
                if lang == "es" else
                f"✅ Showing the {len(top)} cells with highest probability of finding "
                f"survivors alive ({n_total} cells with hope in the zone).")
            if pop_src == "censo_ine":
                st.caption(
                    "📊 Personas en celda: densidad censal INE Venezuela 2011 × "
                    "ocupación HAZUS 18:05 VET. Fuente: ine.gov.ve · Incertidumbre ±30 %."
                    if lang == "es" else
                    "📊 Persons in cell: INE Venezuela 2011 census density × HAZUS "
                    "occupancy at 18:05 VET. Source: ine.gov.ve · Uncertainty ±30 %.")
            st.download_button(t("descargar_csv", lang),
                               con_esperanza.to_csv(index=False).encode("utf-8"),
                               file_name=f"prioridad_{zone_id}.csv", mime="text/csv")

    # ── RECURSOS CRÍTICOS agrupados por área ─────────────────────────────────
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


@st.cache_data(ttl=110, show_spinner=False)
def _cached_zone(zone_id: str, _refresh_salt: int):
    config = load_config()
    return build_zone(get_zone(config, zone_id), config)
