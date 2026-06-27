"""Recursos críticos reales desde OpenStreetMap (Overpass API).

Hospitales, clínicas, estaciones de bomberos/ambulancias y refugios: a dónde
llevar sobrevivientes y qué activos de rescate hay cerca. Datos en vivo.
© colaboradores de OpenStreetMap.
"""
import time
import pandas as pd
import requests

_CACHE: dict = {}  # bbox -> (timestamp, DataFrame)
# Overpass exige un User-Agent descriptivo (etiqueta de uso); sin él responde 406.
HEADERS = {"User-Agent": "ProbabilidadDeVida-SAR/1.0 "
                         "(respuesta humanitaria a terremoto; contacto en repositorio)"}
# Servidores espejo de respaldo: el público gratuito limita peticiones seguidas.
MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _post_overpass(endpoints, query, timeout):
    """Intenta cada endpoint con un reintento; devuelve JSON o lanza la última excepción."""
    last = None
    for url in endpoints:
        for intento in range(2):
            try:
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # 429/504/timeout → reintentar / siguiente espejo
                last = e
                time.sleep(1.5 * (intento + 1))
    raise last

KIND_LABELS = {
    "hospital": "🏥 Hospital", "clinic": "🏥 Clínica",
    "fire_station": "🚒 Bomberos", "ambulance_station": "🚑 Ambulancias",
    "shelter": "⛺ Refugio",
}


def fetch_resources(bbox, endpoint: str, ttl: float = 1800.0,
                    timeout: float = 30.0) -> pd.DataFrame:
    """Recursos de emergencia dentro del bbox [lon_min,lat_min,lon_max,lat_max]."""
    key = tuple(round(x, 4) for x in bbox)
    cached = _CACHE.get(key)
    if cached and (time.time() - cached[0]) < ttl:
        return cached[1]

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

            # Teléfono: varios tags alternativos en OSM
            phone = (tags.get("phone")
                     or tags.get("contact:phone")
                     or tags.get("contact:mobile")
                     or tags.get("telephone")
                     or "")

            # Dirección: addr:full > construida desde partes
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
                "nombre":   tags.get("name", "—"),
                "tipo":     kind,
                "etiqueta": KIND_LABELS.get(kind, kind),
                "lat":      lat,
                "lon":      lon,
                "telefono": phone,
                "direccion": addr_full,
                "web":      web,
            })
    except Exception:
        df = pd.DataFrame(columns=["nombre", "tipo", "etiqueta", "lat", "lon",
                                   "telefono", "direccion", "web"])
        df.attrs["error"] = True
        return df

    df = pd.DataFrame(rows, columns=["nombre", "tipo", "etiqueta", "lat", "lon",
                                     "telefono", "direccion", "web"])
    df.attrs["error"] = False
    _CACHE[key] = (time.time(), df)
    return df
