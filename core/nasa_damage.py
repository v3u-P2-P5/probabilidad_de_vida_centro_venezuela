"""NASA Sentinel-1 SAR — edificios probablemente dañados (Venezuela, jun 2026).

ArcGIS Feature Service público, sin autenticación. Clasificación experimental.
Cobertura parcial: área Caracas + litoral La Guaira (extensión del pase SAR).

Fuente: patrick_rea@NASA via NASA EarthData GIS Portal
Servicio: 202610_s1_likelydmgareas / FeatureServer/0
"""
import requests
import streamlit as st

_QUERY_URL = (
    "https://services7.arcgis.com/WSiUmUhlFx4CtMBB/arcgis/rest/services/"
    "202610_s1_likelydmgareas/FeatureServer/0/query"
)
_HEADERS = {"User-Agent": "ProbabilidadDeVida-SAR/1.0 (humanitarian; contact in repo)"}
_NASA_WEBMAP = (
    "https://gis.earthdata.nasa.gov/portal/apps/mapviewer/index.html"
    "?webmap=0c3d77dd5aae46e4829d9a282477615c"
)


def _centroid(ring: list) -> tuple[float, float]:
    """Centroide del anillo exterior de un polígono [[lon, lat], ...]."""
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def nasa_map_url(lat: float, lon: float, zoom: int = 17) -> str:
    """URL del mapa NASA centrado en este punto exacto."""
    return f"{_NASA_WEBMAP}&center={lon:.5f},{lat:.5f}&zoom={zoom}"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nasa_damage(bbox: tuple) -> list[dict]:
    """Edificios dañados (damage=1) dentro del bbox desde NASA ArcGIS FeatureServer.

    Retorna lista de {lat, lon, prob, label}. Lista vacía ante cualquier fallo
    o si la zona no tiene cobertura SAR — el caller omite la capa en ese caso.

    bbox: (lon_min, lat_min, lon_max, lat_max)
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    params = {
        "where": "damage=1",
        "geometry": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "damage_probability,label",
        "returnGeometry": "true",
        "resultRecordCount": 2000,
        "f": "geojson",
    }
    try:
        r = requests.get(_QUERY_URL, params=params, headers=_HEADERS, timeout=20)
        r.raise_for_status()
        features = r.json().get("features", [])
        out = []
        for feat in features:
            geom  = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            gtype = geom.get("type", "")
            coords = geom.get("coordinates", [])
            if not coords:
                continue
            if gtype == "Polygon":
                ring = coords[0]
            elif gtype == "MultiPolygon":
                ring = coords[0][0]
            else:
                continue
            if len(ring) < 3:
                continue
            lat_c, lon_c = _centroid(ring)
            out.append({
                "lat":   lat_c,
                "lon":   lon_c,
                "prob":  float(props.get("damage_probability") or 0),
                "label": props.get("label", "likely_damaged"),
            })
        return out
    except Exception:
        return []
