"""Réplicas en vivo — gráfico + mapa + tabla, datos reales USGS en tiempo real.

Muestra los sismos recientes cerca del epicentro (USGS FDSN, consulta en vivo).
NADA inventado: si USGS no responde, se marca NO DISPONIBLE con enlace oficial.
Los dos sismos principales (M7.5/M7.2) se marcan aparte para no confundirlos con
réplicas.
"""
from datetime import datetime, timezone

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from core.config import load_config
from core.data_sources import get_aftershocks
from core.sources import fmt_vet_utc, parse_iso
from core.ui import apply_chrome

config = load_config()
lang = apply_chrome(config)
EN = lang == "en"


def T(es, en):
    return en if EN else es


st.title("🌎 " + T("Réplicas en vivo", "Live aftershocks"))
st.caption(T(
    "Sismos recientes cerca del epicentro · datos en vivo de USGS · "
    "los dos eventos principales (M7,5 + M7,2) se marcan aparte.",
    "Recent earthquakes near the epicenter · live USGS data · "
    "the two main events (M7.5 + M7.2) are flagged separately.",
))

# ── Controles ─────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
dias = c1.selectbox(T("Ventana", "Window"),
                    [3, 7, 15, 30], index=1,
                    format_func=lambda d: T(f"últimos {d} días", f"last {d} days"))
minmag = c2.selectbox(T("Magnitud mínima", "Min magnitude"),
                      [2.5, 3.0, 4.0, 4.5], index=0, format_func=lambda m: f"M{m}")
radio = c3.selectbox(T("Radio", "Radius"),
                     [150, 200, 300], index=1, format_func=lambda r: f"{r} km")

data = get_aftershocks(dias_atras=dias, min_magnitud=minmag, radio_km=radio, limite=200)

if not data.get("disponible"):
    st.error(T("Datos de réplicas NO DISPONIBLES ahora mismo. Consulta la fuente oficial:",
               "Aftershock data is NOT AVAILABLE right now. Check the official source:")
             + f"\n\n🔗 [USGS]({data.get('url','https://earthquake.usgs.gov/earthquakes/')})")
    st.stop()

reps = data["replicas"]
df = pd.DataFrame(reps)
if df.empty:
    st.info(T("No hay sismos que cumplan el filtro en esta ventana (según USGS). "
              "Prueba a ampliar la ventana o bajar la magnitud mínima.",
              "No earthquakes match this filter in the window (per USGS). "
              "Try a wider window or a lower minimum magnitude."))
    st.stop()

df["hora"] = pd.to_datetime(df["hora_utc"], utc=True, errors="coerce")
df["tipo"] = df["es_evento_principal"].map(
    lambda p: T("Sismo principal", "Main shock") if p else T("Réplica", "Aftershock"))
replicas_only = df[~df["es_evento_principal"]]

# ── KPIs ──────────────────────────────────────────────────────────────────────
k = st.columns(4)
k[0].metric(T("Sismos en la ventana", "Quakes in window"), int(len(df)))
k[1].metric(T("Réplicas (sin principales)", "Aftershocks (excl. main)"), int(len(replicas_only)))
mag_max_rep = replicas_only["magnitud"].max() if not replicas_only.empty else None
k[2].metric(T("Réplica mayor", "Largest aftershock"),
            f"M{mag_max_rep:.1f}" if pd.notna(mag_max_rep) else "—")
ultimo = df.sort_values("hora", ascending=False).iloc[0]
k[3].metric(T("Más reciente", "Most recent"),
            f"M{ultimo['magnitud']:.1f}" if pd.notna(ultimo["magnitud"]) else "—",
            help=str(ultimo.get("lugar", "")))

# ── Gráfico: magnitud vs tiempo ───────────────────────────────────────────────
st.subheader("📈 " + T("Magnitud en el tiempo", "Magnitude over time"))
try:
    import altair as alt
    base = df.dropna(subset=["hora", "magnitud"])
    chart = (
        alt.Chart(base)
        .mark_circle(opacity=0.85)
        .encode(
            x=alt.X("hora:T", title=T("Hora (UTC)", "Time (UTC)")),
            y=alt.Y("magnitud:Q", title=T("Magnitud", "Magnitude"),
                    scale=alt.Scale(zero=False)),
            size=alt.Size("magnitud:Q", legend=None, scale=alt.Scale(range=[40, 700])),
            color=alt.Color("tipo:N", title="",
                            scale=alt.Scale(domain=[T("Réplica", "Aftershock"),
                                                    T("Sismo principal", "Main shock")],
                                            range=["#e65100", "#b30000"])),
            tooltip=[alt.Tooltip("hora:T", title="UTC"),
                     alt.Tooltip("magnitud:Q", title="M"),
                     alt.Tooltip("lugar:N", title=T("Lugar", "Place")),
                     alt.Tooltip("profundidad_km:Q", title=T("Prof. km", "Depth km"))],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)
except Exception:
    st.scatter_chart(df, x="hora", y="magnitud", color="tipo", height=300)

# ── Mapa de epicentros ────────────────────────────────────────────────────────
st.subheader("🗺️ " + T("Mapa de epicentros", "Epicenter map"))


def _color(mag, principal):
    if principal:
        return "#7b0000"
    if mag is None:
        return "#9e9e9e"
    if mag >= 5:
        return "#b71c1c"
    if mag >= 4:
        return "#e65100"
    if mag >= 3:
        return "#f9a825"
    return "#fdd835"


pts = df.dropna(subset=["lat", "lon"])
if pts.empty:
    st.info(T("Sin coordenadas para mapear.", "No coordinates to map."))
else:
    lat0, lon0 = pts["lat"].mean(), pts["lon"].mean()
    fmap = folium.Map(location=[lat0, lon0], zoom_start=7, tiles="CartoDB positron")
    # Zonas cubiertas (rectángulos de referencia para los rescatistas)
    for z in config["zonas"]:
        lon_min, lat_min, lon_max, lat_max = z["bbox"]
        folium.Rectangle([[lat_min, lon_min], [lat_max, lon_max]],
                         color="#1565c0", weight=1, fill=True, fill_opacity=0.06,
                         tooltip=z["nombre"]).add_to(fmap)
    for _, r in pts.iterrows():
        mag = r["magnitud"]
        principal = bool(r["es_evento_principal"])
        radius = 5 + (float(mag) - 2.0) * 3 if pd.notna(mag) else 5
        popup = folium.Popup(
            f"<b>M{mag} {r.get('magType','')}</b><br>{r.get('lugar','')}<br>"
            f"{r.get('hora_utc','')}<br>"
            + T("Prof.", "Depth") + f": {r.get('profundidad_km','?')} km"
            + (f"<br><a href='{r['evento_url']}' target='_blank'>USGS →</a>"
               if r.get("evento_url") else ""),
            max_width=240)
        folium.CircleMarker(
            [r["lat"], r["lon"]], radius=max(radius, 4),
            color=_color(mag, principal), fill=True,
            fill_color=_color(mag, principal),
            fill_opacity=0.75 if not principal else 0.9, weight=2 if principal else 1,
            popup=popup,
            tooltip=(T("PRINCIPAL ", "MAIN ") if principal else "") + f"M{mag}").add_to(fmap)
    try:
        fmap.fit_bounds([[pts["lat"].min(), pts["lon"].min()],
                         [pts["lat"].max(), pts["lon"].max()]])
    except Exception:
        pass
    st_folium(fmap, use_container_width=True, height=460,
              returned_objects=[], key="aftermap")
    st.caption(T(
        "🔴 oscuro = sismo principal · rojo→naranja→amarillo según magnitud · "
        "🔵 recuadros = zonas cubiertas por la app.",
        "🔴 dark = main shock · red→orange→yellow by magnitude · "
        "🔵 rectangles = zones covered by the app."))

# ── Tabla ─────────────────────────────────────────────────────────────────────
st.subheader("📋 " + T("Listado", "List"))
tbl = df.sort_values("hora", ascending=False).copy()
tbl_view = pd.DataFrame({
    T("Tipo", "Type"): tbl["tipo"],
    T("Magnitud", "Magnitude"): tbl["magnitud"].map(lambda m: f"M{m}" if pd.notna(m) else "—"),
    T("Hora (UTC)", "Time (UTC)"): tbl["hora_utc"],
    T("Lugar", "Place"): tbl["lugar"],
    T("Prof. (km)", "Depth (km)"): tbl["profundidad_km"],
    T("Dist. epicentro (km)", "Dist. epicenter (km)"): tbl["distancia_epicentro_km"],
})
st.markdown(f'<p class="swipe-hint">{T("desliza ➡️", "swipe ➡️")}</p>', unsafe_allow_html=True)
st.dataframe(tbl_view, hide_index=True, use_container_width=True)

# ── Fuente y hora ─────────────────────────────────────────────────────────────
try:
    consulta = fmt_vet_utc(parse_iso(data["hora_consulta"]))
except Exception:
    consulta = data.get("hora_consulta", "")
st.caption(
    "🔗 " + T("Fuente", "Source") + ": "
    f"[{data['fuente']}]({data['url']})  ·  "
    + T("última consulta", "last fetched") + f": {consulta}  ·  "
    + T("se actualiza solo (caché 2 min).", "auto-updates (2 min cache)."))
st.info(T(
    "ℹ️ Datos sísmicos reales de USGS. Las réplicas pueden seguir días o semanas y "
    "debilitar estructuras ya dañadas: extrema precaución cerca de edificios afectados. "
    "Emergencias: 171 o 911.",
    "ℹ️ Real USGS seismic data. Aftershocks may continue for days or weeks and further "
    "weaken already-damaged structures: use extreme caution near affected buildings. "
    "Emergencies: 171 or 911."))
