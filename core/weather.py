"""Condiciones meteorológicas actuales por zona (Open-Meteo, sin API key).

Open-Meteo es una API abierta (CC BY 4.0), gratuita y sin registro.
Los datos se cachean 10 minutos; si la API falla la sección simplemente
no se muestra (degradación elegante, sin romper el resto de la app).
"""
import streamlit as st
import requests
from core.sources import fmt_vet_utc

_URL = "https://api.open-meteo.com/v1/forecast"

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


def _wmo(code: int) -> tuple[str, str]:
    """Devuelve (emoji, texto) para un código WMO, con fallback."""
    return _WMO.get(code, ("🌡️", f"Código {code}"))


@st.cache_data(ttl=600, show_spinner=False)
def get_weather(lat: float, lon: float) -> dict | None:
    """Condiciones actuales de Open-Meteo para la coordenada dada.

    Devuelve dict con temp, precip, wind, icon, condition, fetched_at,
    o None si la API no responde.
    """
    try:
        r = requests.get(
            _URL,
            params={
                "latitude":  round(lat, 4),
                "longitude": round(lon, 4),
                "current":   "temperature_2m,precipitation,windspeed_10m,weathercode",
                "timezone":  "America/Caracas",
                "forecast_days": 1,
            },
            timeout=5,
        )
        r.raise_for_status()
        cur = r.json().get("current", {})
        code = int(cur.get("weathercode", 0))
        icon, condition = _wmo(code)
        return {
            "temp":      cur.get("temperature_2m"),
            "precip":    cur.get("precipitation", 0.0),
            "wind":      cur.get("windspeed_10m"),
            "icon":      icon,
            "condition": condition,
            "fetched_at": fmt_vet_utc(),
        }
    except Exception:
        return None
