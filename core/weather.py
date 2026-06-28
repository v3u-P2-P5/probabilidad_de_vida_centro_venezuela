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
      hourly   → lista de dicts {hora, icon, temp, precip_prob, precip}
      daily    → lista de dicts {dia, icon, condition, tmax, tmin, precip, precip_prob}
    Devuelve None si la API no responde o el parsing falla.
    """
    def _val(lst, i, default=0):
        """Acceso seguro a lista que puede contener None."""
        try:
            v = lst[i]
            return v if v is not None else default
        except Exception:
            return default

    try:
        r = requests.get(
            _URL,
            params={
                "latitude":   round(lat, 4),
                "longitude":  round(lon, 4),
                "current":    "temperature_2m,precipitation,windspeed_10m,weathercode",
                "hourly":     "temperature_2m,precipitation_probability,precipitation,weathercode",
                "daily":      "weather_code,temperature_2m_max,temperature_2m_min,"
                              "precipitation_sum",
                "timezone":   "America/Caracas",
                "forecast_days": 3,
            },
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()

        # ── Condiciones actuales ──────────────────────────────────────────────
        cur  = data.get("current", {})
        icon, condition = _wmo(cur.get("weathercode", 0))
        current = {
            "temp":       cur.get("temperature_2m", 0),
            "precip":     cur.get("precipitation", 0.0),
            "wind":       cur.get("windspeed_10m", 0),
            "icon":       icon,
            "condition":  condition,
            "fetched_at": fmt_vet_utc(),
        }

        # ── Pronóstico horario: próximas 12 h desde ahora ────────────────────
        now_iso = datetime.now(VET).strftime("%Y-%m-%dT%H:00")
        h = data.get("hourly", {})
        times = h.get("time", [])
        wc_h  = h.get("weathercode") or []
        tmp_h = h.get("temperature_2m") or []
        pp_h  = h.get("precipitation_probability") or []
        pr_h  = h.get("precipitation") or []
        try:
            start = next(i for i, t in enumerate(times) if t >= now_iso)
        except StopIteration:
            start = 0
        hourly = []
        for i in range(start, min(start + 13, len(times))):
            ic, _ = _wmo(_val(wc_h, i, 0))
            hourly.append({
                "hora":        _fmt_hora(times[i]),
                "icon":        ic,
                "temp":        _val(tmp_h, i, 0),
                "precip_prob": _val(pp_h, i, 0),
                "precip":      _val(pr_h, i, 0.0),
            })

        # ── Pronóstico diario: mañana y pasado mañana ────────────────────────
        d = data.get("daily", {})
        days    = d.get("time", [])
        today   = datetime.now(VET).strftime("%Y-%m-%d")
        wc_d   = d.get("weather_code") or []
        tmax_d = d.get("temperature_2m_max") or []
        tmin_d = d.get("temperature_2m_min") or []
        psum_d = d.get("precipitation_sum") or []
        daily = []
        for i, day in enumerate(days):
            if day <= today:
                continue
            ic, cond = _wmo(_val(wc_d, i, 0))
            daily.append({
                "dia":       _fmt_dia(day),
                "icon":      ic,
                "condition": cond,
                "tmax":      _val(tmax_d, i, 0),
                "tmin":      _val(tmin_d, i, 0),
                "precip":    _val(psum_d, i, 0.0),
            })
            if len(daily) == 2:
                break

        return {"current": current, "hourly": hourly, "daily": daily}

    except Exception:
        return None
