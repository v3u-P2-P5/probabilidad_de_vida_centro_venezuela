"""Datos de impacto humanitario en tiempo real (fuentes oficiales).

- GDACS: nivel de alerta global y severidad del evento (público, sin registro).
- ReliefWeb (OCHA): últimos reportes de situación con cifras oficiales de
  fallecidos/heridos/desaparecidos/daños. La API v2 exige un *appname aprobado*
  (gratuito, se solicita en https://apidoc.reliefweb.int/parameters#appname).
  Mientras no haya appname aprobado, se degrada con elegancia: se enlaza la
  página oficial del desastre y el feed aparece automáticamente al aprobarlo.

Diseño: SOLO datos reales y atribuidos. Nunca se fabrica un número propio.
Tolerante a fallos: si una fuente cae, se omite (no rompe la app).
"""
import time
from datetime import datetime, timezone

import requests

_HEADERS = {"User-Agent": "ProbabilidadDeVida/1.0 "
                         "(informacion humanitaria post-terremoto Venezuela)"}
_CACHE: dict = {}   # key -> (timestamp, value)


def _cached(key: str, ttl: float):
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    return None


def _store(key: str, value):
    _CACHE[key] = (time.time(), value)
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_gdacs(config: dict) -> dict:
    """Alerta y severidad GDACS. Devuelve dict tolerante a fallos."""
    rcfg = config.get("relief", {})
    ttl = float(rcfg.get("ttl_segundos", 600))
    cached = _cached("gdacs", ttl)
    if cached is not None:
        return cached

    eventid = rcfg.get("gdacs_eventid")
    episodeid = rcfg.get("gdacs_episodeid")
    page = (f"https://www.gdacs.org/report.aspx?eventid={eventid}"
            f"&episodeid={episodeid}&eventtype=EQ")
    out = {"alertlevel": None, "severity": None, "summary": None,
           "datemodified": None, "fetched_at": _now_iso(), "url": page}
    if not eventid:
        return _store("gdacs", out)
    try:
        r = requests.get(
            "https://www.gdacs.org/gdacsapi/api/events/geteventdata",
            params={"eventtype": "EQ", "eventid": eventid, "episodeid": episodeid},
            headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        props = data.get("properties") if isinstance(data, dict) else None
        if not props and isinstance(data, dict):
            feats = data.get("features") or []
            props = feats[0].get("properties", {}) if feats else {}
        if props:
            out["alertlevel"] = props.get("alertlevel")
            sev = props.get("severitydata") or {}
            out["severity"] = sev.get("severitytext")
            out["summary"] = props.get("htmldescription") or props.get("description")
            out["datemodified"] = props.get("datemodified")
    except Exception:
        pass
    return _store("gdacs", out)


def get_reliefweb_reports(config: dict, limit: int = 6) -> dict:
    """Últimos reportes de situación de ReliefWeb (OCHA) para el desastre.

    Devuelve {"reports": [{title, source, date, url}], "fetched_at", "url",
              "needs_appname": bool}. Si la API no está disponible (appname no
    aprobado u otra causa), 'reports' va vacío y se usa el enlace al desastre.
    """
    rcfg = config.get("relief", {})
    ttl = float(rcfg.get("ttl_segundos", 600))
    key = f"reliefweb_{limit}"
    cached = _cached(key, ttl)
    if cached is not None:
        return cached

    disaster = rcfg.get("reliefweb_disaster", "")
    appname = rcfg.get("appname", "")
    page_url = (f"https://reliefweb.int/disaster/{disaster}" if disaster
                else "https://reliefweb.int")
    out = {"reports": [], "fetched_at": _now_iso(), "url": page_url,
           "needs_appname": False}

    if not appname:
        out["needs_appname"] = True
        return _store(key, out)

    params = [
        ("appname", appname),
        ("filter[field]", "primary_country.iso3"),
        ("filter[value]", "VEN"),
        ("query[value]", "earthquake terremoto"),
        ("sort[]", "date.created:desc"),
        ("limit", str(limit)),
        ("fields[include][]", "title"),
        ("fields[include][]", "url_alias"),
        ("fields[include][]", "date.created"),
        ("fields[include][]", "source.name"),
    ]
    try:
        r = requests.get("https://api.reliefweb.int/v2/reports",
                         params=params, headers=_HEADERS, timeout=15)
        if r.status_code == 403:
            out["needs_appname"] = True   # appname no aprobado
            return _store(key, out)
        r.raise_for_status()
        for item in r.json().get("data", []):
            f = item.get("fields", {})
            src = f.get("source") or []
            src_name = src[0].get("name") if src and isinstance(src, list) else ""
            date = (f.get("date") or {}).get("created", "")
            out["reports"].append({
                "title": f.get("title", "—"),
                "source": src_name or "ReliefWeb",
                "date": (date or "")[:10],
                "url": f.get("url_alias") or item.get("href", page_url),
            })
    except Exception:
        pass
    return _store(key, out)
