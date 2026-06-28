"""Condiciones meteorológicas actuales + pronóstico por zona (Open-Meteo, sin API key).

Open-Meteo es una API abierta (CC BY 4.0), gratuita y sin registro.
Una sola llamada devuelve: condiciones actuales, próximas 12 h y próximos 2 días.
Los datos se cachean 10 minutos; si la API falla la sección simplemente
no se muestra (degradación elegante, sin romper el resto de la app).
"""
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st

from core.sources import fmt_vet_utc

_URL = "https://api.open-meteo.com/v1/forecast"
VET  = timezone(timedelta(hours=-4))

# WMO Weather Interpretation Codes → (emoji, texto español)
_WMO = {
    0:  ("☀️",  "Despejado"),
    1:  ("🌤️", "Mayormente despejado"),
    2:  ("⛅",  "Parcialmente nublado"),
    3:  ("☁️",  "Nublado"),
    45: ("🌫️", "Niebla"),
    48: ("🌫️", "Niebla con escarcha"),
    51: ("🌦️", "Llovizna ligera"),
    53: ("🌦️", "Llovizna moderada"),
    55: ("🌦️", "Llovizna intensa"),
    61: ("🌧️", "Lluvia ligera"),
    63: ("🌧️", "Lluvia moderada"),
    65: ("🌧️", "Lluvia intensa"),
    71: ("🌨️", "Nieve ligera"),
    73: ("🌨️", "Nieve moderada"),
    75: ("🌨️", "Nieve intensa"),
    80: ("🌦️", "Chubascos ligeros"),
    81: ("🌦️", "Chubascos moderados"),
    82: ("⛈️",  "Chubascos fuertes"),
    95: ("⛈️",  "Tormenta eléctrica"),
    96: ("⛈️",  "Tormenta con granizo"),
    99: ("⛈️",  "Tormenta con granizo fuerte"),
}

_DIAS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
_MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]


def _wmo(code) -> tuple[str, str]:
    return _WMO.get(int(code) if code is not None else 0, ("🌡️", "—"))


def _fmt_hora(iso: str) -> str:
    """'2026-06-28T14:00' → '14:00'"""
    try:
        return iso[11:16]
    except Exception:
        return iso


def _fmt_dia(date_str: str) -> str:
    """'2026-06-29' → 'Dom 29 jun'"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{_DIAS_ES[d.weekday()]} {d.day} {_MESES_ES[d.month - 1]}"
    except Exception:
        return date_str


@st.cache_data(ttl=600, show_spinner=False)
def get_weather(lat: float, lon: float) -> dict | None:
    """Condiciones actuales + pronóstico horario (12 h) + diario (2 días).

    Devuelve dict con:
      current  → temp, precip, wind, icon, condition, fetched_at
      hourly   → lista de dicts {hora, icon, temp, precip_prob, precip}  (próximas 12 h)
      daily    → lista de dicts {dia, icon, condition, tmax, tmin, precip, precip_prob} (2 días)
    Devuelve None si la API no responde.
    """
    try:
        r = requests.get(
            _URL,
            params={
                "latitude":   round(lat, 4),
                "longitude":  round(lon, 4),
                "current":    "temperature_2m,precipitation,windspeed_10m,weathercode",
                "hourly":     "temperature_2m,precipitation_probability,precipitation,weathercode",
                "daily":      "weathercode_dominant,temperature_2m_max,temperature_2m_min,"
                              "precipitation_sum,precipitation_probability_max",
                "timezone":   "America/Caracas",
                "forecast_days": 3,
            },
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    # ── Condiciones actuales ──────────────────────────────────────────────────
    cur  = data.get("current", {})
    code = cur.get("weathercode", 0)
    icon, condition = _wmo(code)
    current = {
        "temp":       cur.get("temperature_2m"),
        "precip":     cur.get("precipitation", 0.0),
        "wind":       cur.get("windspeed_10m"),
        "icon":       icon,
        "condition":  condition,
        "fetched_at": fmt_vet_utc(),
    }

    # ── Pronóstico horario: próximas 12 h desde ahora ─────────────────────────
    now_iso = (datetime.now(VET)).strftime("%Y-%m-%dT%H:00")
    h = data.get("hourly", {})
    times = h.get("time", [])
    try:
        start = next(i for i, t in enumerate(times) if t >= now_iso)
    except StopIteration:
        start = 0
    hourly = []
    for i in range(start, min(start + 13, len(times))):
        ic, _ = _wmo(h["weathercode"][i])
        hourly.append({
            "hora":        _fmt_hora(times[i]),
            "icon":        ic,
            "temp":        h["temperature_2m"][i],
            "precip_prob": h["precipitation_probability"][i],
            "precip":      h["precipitation"][i],
        })

    # ── Pronóstico diario: mañana y pasado mañana (omitimos hoy) ─────────────
    d = data.get("daily", {})
    days   = d.get("time", [])
    today  = datetime.now(VET).strftime("%Y-%m-%d")
    daily  = []
    for i, day in enumerate(days):
        if day <= today:
            continue
        ic, cond = _wmo(d["weathercode_dominant"][i])
        daily.append({
            "dia":         _fmt_dia(day),
            "icon":        ic,
            "condition":   cond,
            "tmax":        d["temperature_2m_max"][i],
            "tmin":        d["temperature_2m_min"][i],
            "precip":      d["precipitation_sum"][i],
            "precip_prob": d["precipitation_probability_max"][i],
        })
        if len(daily) == 2:
            break

    return {"current": current, "hourly": hourly, "daily": daily}
