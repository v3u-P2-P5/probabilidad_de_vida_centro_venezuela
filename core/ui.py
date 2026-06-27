"""Componentes de interfaz reutilizables (Streamlit + Folium)."""
from datetime import datetime, timedelta, timezone

import folium
import pandas as pd
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from core.config import get_zone, load_config
from core.i18n import IDIOMAS, t
from core.pipeline import build_zone

VET = timezone(timedelta(hours=-4))
PRIORITY_COLORS = {"alta": "#b30000", "media": "#f4a300", "baja": "#2c7fb8"}


def sidebar_language() -> str:
    """Selector de idioma en la barra lateral. Español por defecto."""
    if "lang" not in st.session_state:
        st.session_state.lang = "es"
    codes = list(IDIOMAS.keys())
    lang = st.sidebar.selectbox(
        t("idioma", st.session_state.lang),
        codes,
        index=codes.index(st.session_state.lang),
        format_func=lambda c: IDIOMAS[c],
    )
    st.session_state.lang = lang
    if st.sidebar.button(t("actualizar", lang)):
        st.cache_data.clear()
        st.rerun()
    return lang


@st.cache_data(ttl=120, show_spinner=False)
def _cached_zone(zone_id: str):
    config = load_config()
    return build_zone(get_zone(config, zone_id), config)


def format_quake_time(sismo: dict) -> str:
    """Hora del sismo: VET principal y UTC entre paréntesis (ISO militar)."""
    t0 = datetime.fromisoformat(str(sismo["origen_iso"]).replace("Z", "+00:00"))
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=timezone.utc)
    vet = t0.astimezone(VET).strftime("%Y-%m-%dT%H:%M")
    utc = t0.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return f"{vet} (VET) · {utc} (UTC)"


def _build_map(df: pd.DataFrame, zone: dict, lang: str) -> folium.Map:
    lon_min, lat_min, lon_max, lat_max = zone["bbox"]
    m = folium.Map(
        location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2],
        zoom_start=14, tiles="CartoDB positron", control_scale=True,
    )
    HeatMap(
        df[["lat", "lon", "score_norm"]].values.tolist(),
        radius=18, blur=14, min_opacity=0.25,
    ).add_to(m)
    for _, r in df.nlargest(15, "score_norm").iterrows():
        tipo = t(f"tipo_{r['building_type']}", lang)
        folium.CircleMarker(
            [r["lat"], r["lon"]], radius=6, weight=1,
            color=PRIORITY_COLORS.get(r["prioridad"], "#b30000"),
            fill=True, fill_opacity=0.85,
            popup=folium.Popup(
                f"<b>{r['cell_id']}</b><br>"
                f"{t('col_mmi', lang)}: {r['mmi']:.1f}<br>"
                f"{t('col_tipo', lang)}: {tipo}<br>"
                f"{t('col_pob_celda', lang)}: {int(r['pop_present'])}<br>"
                f"{t('col_score', lang)}: {r['score_norm']:.2f}",
                max_width=240,
            ),
        ).add_to(m)
    return m


def render_zone(zone_id: str) -> None:
    """Renderiza la página completa de una zona."""
    lang = sidebar_language()
    config = load_config()
    zone = get_zone(config, zone_id)
    df, sismo, hs = _cached_zone(zone_id)

    st.title(zone["nombre"])
    st.caption(t("subtitulo_zona", lang))
    if sismo.get("fuente", "sintético") == "sintético":
        st.warning(t("disclaimer_sintetico", lang))

    n_alta = int((df["prioridad"] == "alta").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric(t("kpi_mmi_max", lang), f"{df['mmi'].max():.1f}")
    c2.metric(t("kpi_celdas_alta", lang), f"{n_alta}")
    c3.metric(t("kpi_poblacion_presente", lang), f"{int(df['pop_present'].sum()):,}")

    st_folium(_build_map(df, zone, lang), height=520, use_container_width=True,
              returned_objects=[], key=f"map_{zone_id}")

    st.caption(
        f"{t('leyenda', lang)}: "
        f"🔴 {t('prioridad_alta', lang)} · 🟠 {t('prioridad_media', lang)} · "
        f"🔵 {t('prioridad_baja', lang)}  —  {t('nota_modelo', lang)}"
    )

    st.subheader(t("tabla_prioridad", lang))
    top = df.nlargest(20, "score_norm").copy()
    top["building_type"] = top["building_type"].map(lambda k: t(f"tipo_{k}", lang))
    top["prioridad"] = top["prioridad"].map(lambda k: t(f"prioridad_{k}", lang))
    view = top[["cell_id", "lat", "lon", "mmi", "building_type",
                "pop_present", "prioridad", "score_norm"]].rename(columns={
        "cell_id": t("col_celda", lang), "lat": t("col_lat", lang),
        "lon": t("col_lon", lang), "mmi": t("col_mmi", lang),
        "building_type": t("col_tipo", lang), "pop_present": t("col_pob_celda", lang),
        "prioridad": t("col_prioridad", lang), "score_norm": t("col_score", lang),
    })
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button(
        t("descargar_csv", lang),
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"prioridad_{zone_id}.csv", mime="text/csv",
    )
