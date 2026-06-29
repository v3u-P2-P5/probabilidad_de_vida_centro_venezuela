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

# Mapa renderizado con ArcGIS JS API 4.29 (CDN público de Esri).
# No incrustamos la página de NASA — cargamos sus datos directamente con
# la librería oficial, exactamente como hacen los sitios profesionales con
# Google Maps o Mapbox.
_MAP_HTML = f"""<!DOCTYPE html>
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
  <div id="viewDiv"><div id="loading">Cargando mapa NASA…</div></div>
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
          "No se pudo cargar el mapa. "
          + '<a href="{_NASA_URL}" target="_blank">Abrir en nueva pestaña →</a>';
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

# Mapa ArcGIS JS — si el CDN de Esri no carga, muestra el link de fallback
components.html(_MAP_HTML, height=620, scrolling=False)

st.divider()

if lang == "en":
    st.caption(
        f"[👉 Open full NASA map in new tab]({_NASA_URL}) · "
        "Source: NASA EarthData GIS · Sentinel-1 SAR · "
        "patrick_rea@NASA · public domain (17 USC § 105) · "
        "Map rendered via [ArcGIS JS API 4.29](https://developers.arcgis.com/javascript/) (Esri)"
    )
else:
    st.caption(
        f"[👉 Abrir mapa NASA completo en nueva pestaña]({_NASA_URL}) · "
        "Fuente: NASA EarthData GIS · Sentinel-1 SAR · "
        "patrick_rea@NASA · dominio público (17 USC § 105) · "
        "Mapa renderizado con [ArcGIS JS API 4.29](https://developers.arcgis.com/javascript/) (Esri)"
    )
