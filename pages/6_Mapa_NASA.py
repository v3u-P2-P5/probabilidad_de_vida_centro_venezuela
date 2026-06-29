"""Mapa interactivo NASA — Sentinel-1 SAR: edificios dañados Venezuela 2026.

Usa la ArcGIS JS API 4.x cargada desde CDN para renderizar el WebMap
directamente en un componente HTML de Streamlit, evitando el bloqueo
X-Frame-Options del portal NASA.
"""
import streamlit as st
import streamlit.components.v1 as components

from core.config import load_config
from core.ui import apply_chrome

_NASA_URL = (
    "https://gis.earthdata.nasa.gov/portal/apps/mapviewer/index.html"
    "?webmap=0c3d77dd5aae46e4829d9a282477615c"
)
_WEBMAP_ID   = "0c3d77dd5aae46e4829d9a282477615c"
_PORTAL_URL  = "https://gis.earthdata.nasa.gov/portal"

def _build_map_html(lang: str) -> str:
    """Devuelve el HTML del mapa ArcGIS JS con textos en el idioma correcto."""
    # Cargamos los datos directamente con la ArcGIS JS API (CDN Esri) —
    # NO incrustamos la página de NASA, así que no aplica X-Frame-Options.
    loading_txt = "Loading NASA map…" if lang == "en" else "Cargando mapa NASA…"
    error_txt   = "Could not load map. " if lang == "en" else "No se pudo cargar el mapa. "
    open_tab    = "Open in new tab →"   if lang == "en" else "Abrir en nueva pestaña →"
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
  <link rel="stylesheet"
        href="https://js.arcgis.com/4.29/esri/themes/light/main.css">
  <script src="https://js.arcgis.com/4.29/"></script>
  <style>
    html, body, #viewDiv {{
      padding: 0; margin: 0;
      height: 100%; width: 100%;
      font-family: sans-serif;
    }}
    #loading {{
      position: absolute; top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      color: #555; font-size: 14px;
    }}
  </style>
</head>
<body>
  <div id="viewDiv"><div id="loading">{loading_txt}</div></div>
  <script>
    require([
      "esri/WebMap",
      "esri/views/MapView",
      "esri/config"
    ], function(WebMap, MapView, esriConfig) {{

      esriConfig.portalUrl = "{_PORTAL_URL}";

      const webmap = new WebMap({{
        portalItem: {{
          id: "{_WEBMAP_ID}",
          portal: {{ url: "{_PORTAL_URL}" }}
        }}
      }});

      const view = new MapView({{
        container: "viewDiv",
        map: webmap,
        ui: {{ components: ["zoom", "compass", "attribution"] }}
      }});

      view.when(function() {{
        document.getElementById("loading").style.display = "none";
      }}, function(err) {{
        document.getElementById("loading").innerHTML =
          "{error_txt}"
          + '<a href="{_NASA_URL}" target="_blank">{open_tab}</a>';
      }});
    }});
  </script>
</body>
</html>"""

config = load_config()
lang   = apply_chrome(config)

if lang == "en":
    st.title("🛰️ NASA Satellite Damage Map")
    st.caption(
        "Sentinel-1 SAR analysis — structural damage probability · "
        "Venezuela double earthquake June 2026 · "
        "**Experimental · unvalidated in field · NASA EarthData GIS**"
    )
    st.info(
        "Individual building footprints classified by damage probability "
        "from before/after SAR imagery. "
        "**Red ≥ 75 % · Orange 50–75 % · Amber < 50 %.** "
        "Partial coverage (Caracas + La Guaira coast). "
        "Click any building for details."
    )
else:
    st.title("🛰️ Mapa de Daños por Satélite (NASA)")
    st.caption(
        "Análisis Sentinel-1 SAR — probabilidad de daño estructural · "
        "doble sismo Venezuela jun 2026 · "
        "**Experimental · sin validación en campo · NASA EarthData GIS**"
    )
    st.info(
        "Huellas de edificios individuales clasificadas por probabilidad de daño "
        "a partir de imágenes SAR antes/después. "
        "**Rojo ≥ 75 % · Naranja 50–75 % · Ámbar < 50 %.** "
        "Cobertura parcial (Caracas + litoral La Guaira). "
        "Haz clic en un edificio para ver los detalles."
    )

# ── Leyenda de colores ────────────────────────────────────────────────────────
_LEGEND_ITEMS = [
    ("#c62828", "≥ 75 %", "Likely destroyed"        if lang == "en" else "Probable destrucción"),
    ("#e65100", "50–74 %","Heavily / mod. damaged"   if lang == "en" else "Daño grave / moderado"),
    ("#f9a825", "< 50 %", "Possibly damaged"         if lang == "en" else "Posiblemente dañado"),
]
_legend_title = "Map color key — damage probability" if lang == "en" else "Leyenda de colores — probabilidad de daño"
st.markdown(
    f"<p style='font-size:0.8rem;font-weight:600;margin-bottom:4px'>{_legend_title}</p>"
    + "".join(
        f"<span style='display:inline-flex;align-items:center;gap:5px;"
        f"margin-right:14px;font-size:0.8rem;'>"
        f"<span style='display:inline-block;width:14px;height:14px;border-radius:50%;"
        f"background:{color};opacity:0.85;flex-shrink:0'></span>"
        f"<b>{pct}</b>&nbsp;{label}</span>"
        for color, pct, label in _LEGEND_ITEMS
    ),
    unsafe_allow_html=True,
)

# Mapa ArcGIS JS — si el CDN de Esri no carga, muestra el link de fallback
components.html(_build_map_html(lang), height=620, scrolling=False)

st.divider()

# ── Fuentes / Sources ────────────────────────────────────────────────────────
if lang == "en":
    st.subheader("Sources")
    st.markdown(
        "| # | Source | Notes |\n"
        "|---|--------|-------|\n"
        "| 1 | [NASA EarthData GIS — Structural Damage Probability Map (Sentinel-1 SAR)]"
        f"({_NASA_URL}) | Before/after SAR analysis, building-level damage probability. "
        "Author: patrick_rea@NASA. **Public domain** (17 USC § 105). |\n"
        "| 2 | [NASA Disasters Program — Venezuela 2026 Activation](https://disasters.nasa.gov/) "
        "| Coordination portal for the NASA Disasters response to the June 2026 event. |\n"
        "| 3 | [Copernicus EMS — EMSR884 (damage mapping, Venezuela)]"
        "(https://mapping.emergency.copernicus.eu/news/earthquake-in-venezuela-emsr884/) "
        "| European Commission satellite damage cartography. "
        "Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). |\n"
        "| 4 | [Maxar/Vantor Open Data — Pre/post event imagery]"
        "(https://vantor.com/company/open-data-program/) "
        "| Very-high-resolution optical imagery released under the Open Data Program. |\n"
        "| 5 | [ArcGIS JS API 4.29](https://developers.arcgis.com/javascript/) (Esri) "
        "| Map rendering library. Map data © Esri & contributors. |"
    )
    st.caption(
        f"[👉 Open full NASA map in new tab]({_NASA_URL})  ·  "
        "Experimental analysis — not validated in the field — do not use as sole basis for "
        "damage assessment or resource allocation."
    )
else:
    st.subheader("Fuentes")
    st.markdown(
        "| # | Fuente | Notas |\n"
        "|---|--------|-------|\n"
        "| 1 | [NASA EarthData GIS — Mapa de probabilidad de daño estructural (Sentinel-1 SAR)]"
        f"({_NASA_URL}) | Análisis SAR antes/después, probabilidad de daño por edificio. "
        "Autor: patrick_rea@NASA. **Dominio público** (17 USC § 105). |\n"
        "| 2 | [NASA Disasters Program — Activación Venezuela 2026](https://disasters.nasa.gov/) "
        "| Portal de coordinación de la respuesta NASA al evento de junio 2026. |\n"
        "| 3 | [Copernicus EMS — EMSR884 (cartografía de daño, Venezuela)]"
        "(https://mapping.emergency.copernicus.eu/news/earthquake-in-venezuela-emsr884/) "
        "| Cartografía de daño por satélite de la Comisión Europea. "
        "Licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). |\n"
        "| 4 | [Maxar/Vantor Open Data — Imágenes pre/post evento]"
        "(https://vantor.com/company/open-data-program/) "
        "| Imágenes ópticas de muy alta resolución publicadas bajo el Open Data Program. |\n"
        "| 5 | [ArcGIS JS API 4.29](https://developers.arcgis.com/javascript/) (Esri) "
        "| Librería de renderizado del mapa. Datos cartográficos © Esri y colaboradores. |"
    )
    st.caption(
        f"[👉 Abrir mapa NASA completo en nueva pestaña]({_NASA_URL})  ·  "
        "Análisis experimental — sin validación en campo — no usar como única base para "
        "evaluación de daños o asignación de recursos."
    )
