"""Utilidades geográficas: rejilla por bbox y distancias."""
import numpy as np
import pandas as pd

M_PER_DEG_LAT = 111_320.0  # metros por grado de latitud (aprox.)

# Ciudades grandes de referencia (lat, lon) para dar contexto geográfico al
# público y a las skills, sin tener que importar app.py.
CIUDADES_REF = {
    "Puerto Cabello": (10.4731, -68.0125),
    "Valencia":       (10.1620, -68.0077),
    "Maracay":        (10.2469, -67.5958),
    "Barquisimeto":   (10.0647, -69.3301),
    "Caracas":        (10.4806, -66.9036),
}


def make_grid(bbox, cell_m: float) -> pd.DataFrame:
    """Genera centros de celda en una rejilla regular sobre el bbox.

    bbox = [lon_min, lat_min, lon_max, lat_max]. Devuelve DataFrame(lat, lon, cell_id).
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    lat_c = (lat_min + lat_max) / 2.0
    dlat = cell_m / M_PER_DEG_LAT
    dlon = cell_m / (M_PER_DEG_LAT * np.cos(np.radians(lat_c)))
    lats = np.arange(lat_min + dlat / 2, lat_max, dlat)
    lons = np.arange(lon_min + dlon / 2, lon_max, dlon)
    glon, glat = np.meshgrid(lons, lats)
    df = pd.DataFrame({"lat": glat.ravel(), "lon": glon.ravel()})
    df["cell_id"] = [f"c{i:05d}" for i in range(len(df))]
    return df


def haversine_m(lat1, lon1, lat2, lon2):
    """Distancia en metros (vectorizable con numpy)."""
    R = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(np.asarray(lat2) - np.asarray(lat1))
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))
