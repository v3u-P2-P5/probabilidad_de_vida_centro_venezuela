"""Fuentes de datos de sacudimiento.

- Real: metadatos del evento desde USGS (FDSN). La integración del raster
  ShakeMap completo queda como TODO; aquí usamos epicentro/magnitud reales
  con un campo de intensidad modelado (IPE simplificada).
- Fallback: parámetros del config.yaml.
"""
from datetime import datetime
import numpy as np
import requests

from core.geo import haversine_m

USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def fetch_usgs_event(event_id: str, timeout: float = 8.0) -> dict | None:
    """Trae magnitud/epicentro/profundidad/hora de un evento USGS. None si falla."""
    try:
        r = requests.get(
            USGS_EVENT_URL,
            params={"eventid": event_id, "format": "geojson"},
            timeout=timeout,
        )
        r.raise_for_status()
        d = r.json()
        lon, lat, depth = d["geometry"]["coordinates"]
        props = d["properties"]
        return {
            "magnitud": props.get("mag"),
            "profundidad_km": depth,
            "epicentro": {"lat": lat, "lon": lon},
            "origen_iso": datetime.utcfromtimestamp(props["time"] / 1000).isoformat() + "Z",
            "fuente": "USGS",
        }
    except Exception:
        return None


def get_sismo(config: dict) -> dict:
    """Devuelve los parámetros del sismo (reales si están disponibles)."""
    sismo = dict(config["sismo"])
    if sismo.get("usar_datos_reales") and sismo.get("usgs_event_id"):
        real = fetch_usgs_event(sismo["usgs_event_id"])
        if real:
            sismo.update({k: v for k, v in real.items() if v is not None})
    sismo.setdefault("fuente", "sintético")
    return sismo


def synthetic_mmi(lat, lon, sismo: dict):
    """Campo de intensidad MMI modelado (IPE simplificada tipo Allen et al.).

    I = a + b·M − c·ln(R), con R = distancia hipocentral. Clip a [1, 10].
    Funciona con epicentro/magnitud reales o del config.
    """
    epi = sismo["epicentro"]
    M = float(sismo["magnitud"])
    depth = float(sismo.get("profundidad_km", 10.0))
    d_km = haversine_m(lat, lon, epi["lat"], epi["lon"]) / 1000.0
    R = np.sqrt(d_km ** 2 + depth ** 2)
    mmi = 1.0 + 1.5 * M - 1.3 * np.log(np.maximum(R, 1.0))
    return np.clip(mmi, 1.0, 10.0)
