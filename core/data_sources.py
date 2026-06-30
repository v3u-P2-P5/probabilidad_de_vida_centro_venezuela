"""Cliente USGS: evento, ShakeMap, PAGER (víctimas) y ground-failure.

Soporta secuencia sísmica (sismo doble): get_sismos() devuelve todos los eventos
principales; get_sismo() devuelve el de mayor magnitud como referencia.
Datos OFICIALES y en vivo (FDSN event API).
"""
from datetime import datetime, timedelta, timezone
import numpy as np
import requests
import streamlit as st

from core.geo import haversine_m

USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USGS_COUNT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/count"

# Centro de la secuencia (epicentro M7.5) y ids de los DOS sismos principales:
# se usan para anclar la consulta de réplicas y para NO etiquetar los mainshocks
# como réplicas.
EPICENTRO_REF = (10.4351, -68.4716)            # (lat, lon)
MAINSHOCK_IDS = frozenset({"us6000t7zp", "us6000t7zc"})


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
        "origen_iso": datetime.fromtimestamp(p["time"] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_events(event_ids: tuple, timeout: float = 12.0) -> list:
    """Cached USGS fetch — keyed by event IDs so all zones share the same result."""
    eventos = []
    for eid in event_ids:
        e = get_event(eid, timeout=timeout)
        if e:
            eventos.append(e)
    return eventos


def get_sismos(config: dict, timeout: float = 12.0) -> list:
    """Devuelve todos los eventos de la secuencia sísmica (para combinar ShakeMaps)."""
    sismo_cfg = config["sismo"]
    if not sismo_cfg.get("usar_datos_reales"):
        return []
    ids = tuple(eid for eid in (sismo_cfg.get("usgs_event_ids") or [sismo_cfg.get("usgs_event_id")]) if eid)
    return _fetch_events(ids, timeout=timeout)


def get_sismo(config: dict) -> dict:
    """Parámetros del sismo principal (mayor magnitud): reales si posible, respaldo si no."""
    sismo = dict(config["sismo"])
    if sismo.get("usar_datos_reales"):
        eventos = get_sismos(config)
        if eventos:
            principal = max(eventos, key=lambda e: e.get("magnitud") or 0)
            secundarios = [e for e in eventos if e["id"] != principal["id"]]
            sismo.update({k: v for k, v in principal.items() if v is not None})
            if secundarios:
                sismo["sismos_adicionales"] = secundarios
            return sismo
    sismo.setdefault("fuente", "respaldo (config)")
    return sismo


@st.cache_data(ttl=120, show_spinner=False)
def get_aftershocks(dias_atras: int = 3, min_magnitud: float = 2.5,
                    radio_km: int = 200, limite: int = 50,
                    timeout: float = 12.0) -> dict:
    """Réplicas (y mainshocks) reales EN VIVO cerca del epicentro, vía USGS FDSN.

    Devuelve solo eventos que USGS reporta; lista vacía si no hay ninguno en la
    ventana (nunca inventa). Marca es_evento_principal para no confundir los
    sismos M7.5/M7.2 con réplicas. Caché 2 min para no martillar USGS.
    """
    now = datetime.now(timezone.utc)
    lat0, lon0 = EPICENTRO_REF
    starttime = (now - timedelta(days=dias_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {"format": "geojson", "latitude": lat0, "longitude": lon0,
              "maxradiuskm": radio_km, "starttime": starttime,
              "minmagnitude": min_magnitud, "orderby": "time", "limit": limite}
    base = {"fuente": "USGS FDSN Event API", "url": USGS_EVENT_URL,
            "hora_consulta": now.isoformat(),
            "parametros_usados": {"dias_atras": dias_atras, "min_magnitud": min_magnitud,
                                  "radio_km": radio_km}}
    try:
        r = requests.get(USGS_EVENT_URL, params=params, timeout=timeout)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return {**base, "disponible": False, "replicas": [], "total": 0, "error": "fallo de red"}

    reps = []
    for f in d.get("features", []):
        p = f.get("properties", {}) or {}
        coords = (f.get("geometry", {}) or {}).get("coordinates") or [None, None, None]
        lon, lat, depth = (list(coords) + [None, None, None])[:3]
        t = p.get("time")
        hora = (datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if t else None)
        dist = (round(haversine_m(lat, lon, lat0, lon0) / 1000.0, 1)
                if lat is not None and lon is not None else None)
        eid = f.get("id")
        reps.append({
            "id": eid, "magnitud": p.get("mag"), "magType": p.get("magType"),
            "hora_utc": hora, "lugar": p.get("place"), "profundidad_km": depth,
            "lat": lat, "lon": lon, "distancia_epicentro_km": dist,
            "tsunami": p.get("tsunami"), "status": p.get("status"),
            "evento_url": p.get("url"), "es_evento_principal": eid in MAINSHOCK_IDS,
        })
    return {**base, "disponible": True, "replicas": reps, "total": len(reps),
            "url": (d.get("metadata", {}) or {}).get("url", USGS_EVENT_URL)}


@st.cache_data(ttl=120, show_spinner=False)
def get_aftershock_resumen(dias_atras: int = 7, min_magnitud: float = 2.5,
                           radio_km: int = 200, timeout: float = 12.0) -> dict:
    """Conteo REAL de sismos en la ventana + el de mayor magnitud (USGS count+query)."""
    now = datetime.now(timezone.utc)
    lat0, lon0 = EPICENTRO_REF
    starttime = (now - timedelta(days=dias_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")
    base_params = {"format": "geojson", "latitude": lat0, "longitude": lon0,
                   "maxradiuskm": radio_km, "starttime": starttime, "minmagnitude": min_magnitud}
    out = {"fuente": "USGS FDSN Event API (count + query)", "url": USGS_EVENT_URL,
           "hora_consulta": now.isoformat(),
           "ventana": {"dias_atras": dias_atras, "min_magnitud": min_magnitud, "radio_km": radio_km}}
    try:
        rc = requests.get(USGS_COUNT_URL, params=base_params, timeout=timeout)
        rc.raise_for_status()
        total = int(rc.json().get("count", 0))
    except Exception:
        return {**out, "disponible": False, "total_sismos": None, "max_magnitud": None}
    # 'total_sismos' cuenta TODOS los eventos de la ventana, incluidos los 2
    # principales (M7.5/M7.2) si caen dentro: NO es solo réplicas ni una predicción.
    res = {**out, "disponible": True, "total_sismos": total, "incluye_principales": True,
           "nota_conteo": ("Conteo PASADO de sismos en la ventana; incluye los 2 sismos "
                           "principales si caen dentro. No es una predicción de réplicas futuras."),
           "max_magnitud": None, "max_magnitud_hora_utc": None, "max_magnitud_lugar": None,
           "max_magnitud_evento_url": None, "max_es_evento_principal": None}
    if total > 0:
        try:
            rq = requests.get(USGS_EVENT_URL,
                              params={**base_params, "orderby": "magnitude", "limit": 1},
                              timeout=timeout)
            rq.raise_for_status()
            feats = rq.json().get("features", [])
            if feats:
                top = feats[0]; p = top.get("properties", {}) or {}
                t = p.get("time"); eid = top.get("id")
                res.update({
                    "max_magnitud": p.get("mag"),
                    "max_magnitud_hora_utc": (datetime.fromtimestamp(t / 1000, timezone.utc)
                                              .strftime("%Y-%m-%dT%H:%M:%SZ") if t else None),
                    "max_magnitud_lugar": p.get("place"),
                    "max_magnitud_evento_url": p.get("url"),
                    "max_es_evento_principal": eid in MAINSHOCK_IDS,
                })
        except Exception:
            pass
    return res


def synthetic_mmi(lat, lon, sismo: dict):
    """IPE simplificada — SOLO para modo demostración (no usar en operativo)."""
    epi = sismo["epicentro"]
    M = float(sismo["magnitud"])
    depth = float(sismo.get("profundidad_km", 10.0))
    d_km = haversine_m(lat, lon, epi["lat"], epi["lon"]) / 1000.0
    R = np.sqrt(d_km ** 2 + depth ** 2)
    return np.clip(1.0 + 1.5 * M - 1.3 * np.log(np.maximum(R, 1.0)), 1.0, 10.0)
