"""Cliente USGS: evento, ShakeMap, PAGER (víctimas) y ground-failure.

Datos OFICIALES y en vivo (FDSN event API). Una sola consulta estructura todo.
"""
from datetime import datetime
import numpy as np
import requests

from core.geo import haversine_m

USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def get_event(event_id: str, timeout: float = 12.0) -> dict | None:
    """Estructura magnitud, epicentro, hora, PAGER, ground-failure y URL del ShakeMap."""
    try:
        r = requests.get(USGS_EVENT_URL,
                         params={"eventid": event_id, "format": "geojson"},
                         timeout=timeout)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None

    p = d["properties"]
    lon, lat, depth = d["geometry"]["coordinates"]
    prods = p.get("products", {})

    out = {
        "id": d.get("id"),
        "magnitud": p.get("mag"),
        "profundidad_km": depth,
        "epicentro": {"lat": lat, "lon": lon},
        "origen_iso": datetime.utcfromtimestamp(p["time"] / 1000).isoformat() + "Z",
        "lugar": p.get("place"),
        "url": p.get("url"),
        "alert_pager": p.get("alert"),
        "mmi_max": p.get("mmi"),
        "felt": p.get("felt"),
        "fuente": "USGS",
    }

    sm = prods.get("shakemap")
    if sm:
        g = sm[0]["contents"].get("download/grid.xml")
        out["shakemap_grid_url"] = g["url"] if g else None
        out["shakemap_version"] = sm[0]["properties"].get("version")

    pg = prods.get("losspager")
    if pg:
        out["pager"] = {"alertlevel": pg[0]["properties"].get("alertlevel"),
                        "maxmmi": pg[0]["properties"].get("maxmmi")}

    gf = prods.get("ground-failure")
    if gf:
        pr = gf[0]["properties"]
        out["ground_failure"] = {
            "landslide_alert": pr.get("landslide-alert"),
            "landslide_pop": pr.get("landslide-population-alert-value"),
            "liquefaction_alert": pr.get("liquefaction-alert"),
            "liquefaction_pop": pr.get("liquefaction-population-alert-value"),
        }
    return out


def get_sismo(config: dict) -> dict:
    """Parámetros del sismo: reales (USGS) si es posible, si no los de respaldo."""
    sismo = dict(config["sismo"])
    if sismo.get("usar_datos_reales") and sismo.get("usgs_event_id"):
        real = get_event(sismo["usgs_event_id"])
        if real:
            sismo.update({k: v for k, v in real.items() if v is not None})
            return sismo
    sismo.setdefault("fuente", "respaldo (config)")
    return sismo


def synthetic_mmi(lat, lon, sismo: dict):
    """IPE simplificada — SOLO para modo demostración (no usar en operativo)."""
    epi = sismo["epicentro"]
    M = float(sismo["magnitud"])
    depth = float(sismo.get("profundidad_km", 10.0))
    d_km = haversine_m(lat, lon, epi["lat"], epi["lon"]) / 1000.0
    R = np.sqrt(d_km ** 2 + depth ** 2)
    return np.clip(1.0 + 1.5 * M - 1.3 * np.log(np.maximum(R, 1.0)), 1.0, 10.0)
