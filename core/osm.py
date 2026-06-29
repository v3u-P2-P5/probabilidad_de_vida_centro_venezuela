"""Recursos críticos reales desde OpenStreetMap (Overpass API).

Hospitales, clínicas, estaciones de bomberos/ambulancias y refugios: a dónde
llevar sobrevivientes y qué activos de rescate hay cerca. Datos en vivo.
© colaboradores de OpenStreetMap.
"""
import pandas as pd
import requests
import streamlit as st
# Overpass exige un User-Agent descriptivo (etiqueta de uso); sin él responde 406.
HEADERS = {"User-Agent": "ProbabilidadDeVida-SAR/1.0 "
                         "(respuesta humanitaria a terremoto; contacto en repositorio)"}
# Servidores espejo de respaldo: el público gratuito limita peticiones seguidas.
MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _post_overpass(endpoints, query, timeout):
    """Intenta cada endpoint con un reintento; devuelve JSON o lanza la última excepción.

    Acota el peor caso: sin el sleep final inútil (antes esperaba ~3s justo antes
    de lanzar la excepción) y con timeout (connect, read) separado para fallar
    rápido ante un host inalcanzable en vez de colgar el render.
    """
    import time
    last = None
    n_endpoints = len(endpoints)
    for i_url, url in enumerate(endpoints):
        for intento in range(2):
            try:
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # 429/504/timeout → reintentar / siguiente espejo
                last = e
                ultimo = (i_url == n_endpoints - 1) and (intento == 1)
                if not ultimo:                       # no dormir tras el último intento
                    time.sleep(1.5 * (intento + 1))
    raise last

KIND_LABELS = {
    "hospital": "🏥 Hospital", "clinic": "🏥 Clínica",
    "fire_station": "🚒 Bomberos", "ambulance_station": "🚑 Ambulancias",
    "shelter": "⛺ Refugio",
}
KIND_LABELS_EN = {
    "hospital": "🏥 Hospital", "clinic": "🏥 Clinic",
    "fire_station": "🚒 Fire Station", "ambulance_station": "🚑 Ambulance Station",
    "shelter": "⛺ Shelter",
}

# Orden de presentación por tipo (prioridad SAR)
KIND_ORDER = ["hospital", "ambulance_station", "clinic", "fire_station", "shelter"]


_SECTOR_GRID = [
    ["Suroeste", "Sur",    "Sureste"],
    ["Oeste",    "Centro", "Este"   ],
    ["Noroeste", "Norte",  "Noreste"],
]
_SECTOR_ES_TO_EN = {
    "Suroeste": "Southwest", "Sur": "South",    "Sureste": "Southeast",
    "Oeste":    "West",      "Centro": "Center", "Este":    "East",
    "Noroeste": "Northwest", "Norte": "North",   "Noreste": "Northeast",
}


def translate_area(area: str) -> str:
    """Translate a Spanish grid-sector label to English; OSM neighbourhood names pass through."""
    if not isinstance(area, str) or not area.startswith("Sector "):
        return area or ""
    return "Sector " + _SECTOR_ES_TO_EN.get(area[7:], area[7:])


def _geo_sector(lat: float, lon: float, bbox: list) -> str:
    """Cuadrícula 3×3 dentro del bbox → hasta 9 sectores en puntos cardinales."""
    lon_min, lat_min, lon_max, lat_max = bbox
    lon_span = lon_max - lon_min
    lat_span = lat_max - lat_min
    frac_lon = (lon - lon_min) / lon_span if lon_span else 0.5
    frac_lat = (lat - lat_min) / lat_span if lat_span else 0.5
    col = 0 if frac_lon < 0.33 else (1 if frac_lon < 0.67 else 2)
    row = 0 if frac_lat < 0.33 else (1 if frac_lat < 0.67 else 2)
    return "Sector " + _SECTOR_GRID[row][col]


def assign_areas(df: pd.DataFrame, bbox: list) -> pd.DataFrame:
    """Llena columna 'area' usando tags OSM; fallback a sector geográfico."""
    def _area(row):
        # Tags OSM de barrio/sector, de más a menos específico
        for tag in ("neighbourhood", "suburb", "quarter", "district"):
            val = row.get(tag, "")
            if val:
                return val.strip().title()
        return _geo_sector(row["lat"], row["lon"], bbox)

    df = df.copy()
    df["area"] = df.apply(_area, axis=1)
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_resources(bbox, endpoint: str, ttl: float = 1800.0,
                    timeout=(4, 15)) -> pd.DataFrame:
    """Recursos de emergencia dentro del bbox [lon_min,lat_min,lon_max,lat_max]."""
    lon_min, lat_min, lon_max, lat_max = bbox
    bb = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    query = f"""
    [out:json][timeout:25];
    (
      nwr["amenity"~"^(hospital|clinic|fire_station)$"]({bb});
      nwr["emergency"="ambulance_station"]({bb});
      nwr["amenity"="shelter"]["social_facility"!~"."]({bb});
    );
    out center tags;
    """
    rows = []
    try:
        data = _post_overpass([endpoint] + MIRRORS, query, timeout)
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            kind = tags.get("amenity") or tags.get("emergency") or "shelter"
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue

            phone = (tags.get("phone")
                     or tags.get("contact:phone")
                     or tags.get("contact:mobile")
                     or tags.get("telephone")
                     or "")

            addr_full = tags.get("addr:full", "")
            if not addr_full:
                parts = [tags.get("addr:street", ""),
                         tags.get("addr:housenumber", ""),
                         tags.get("addr:city", ""),
                         tags.get("addr:state", "")]
                addr_full = ", ".join(p for p in parts if p)

            web = (tags.get("website")
                   or tags.get("contact:website")
                   or tags.get("url")
                   or "")

            rows.append({
                "nombre":        tags.get("name", "—"),
                "tipo":          kind,
                "etiqueta":      KIND_LABELS.get(kind, kind),
                "etiqueta_en":   KIND_LABELS_EN.get(kind, kind),
                "lat":           lat,
                "lon":           lon,
                "telefono":      phone,
                "direccion":     addr_full,
                "web":           web,
                "neighbourhood": tags.get("addr:neighbourhood", ""),
                "suburb":        tags.get("addr:suburb", ""),
                "quarter":       tags.get("addr:quarter", ""),
                "district":      tags.get("addr:district", ""),
            })
    except Exception:
        df = pd.DataFrame(columns=["nombre", "tipo", "etiqueta", "etiqueta_en", "lat", "lon",
                                   "telefono", "direccion", "web",
                                   "neighbourhood", "suburb", "quarter", "district"])
        df.attrs["error"] = True
        return df

    df = pd.DataFrame(rows)
    df.attrs["error"] = False
    return df
