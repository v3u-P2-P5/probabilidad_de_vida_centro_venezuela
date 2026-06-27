"""Descarga y parseo del ShakeMap real de USGS (grid.xml).

El grid.xml es una malla regular lat/lon con MMI/PGA/PGV por punto. Aquí se
interpola la MMI MEDIDA sobre la rejilla de análisis de cada zona. Esto NO es
un modelo: es la intensidad oficial publicada por USGS.
"""
import re
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "shakemap_grid.xml"


def download_grid(url: str, dest: Path = CACHE, ttl: float = 300.0,
                  timeout: float = 30.0) -> Path:
    """Descarga grid.xml si la copia local está vencida (TTL)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) < ttl
    if not fresh:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def parse_grid(path: Path = CACHE) -> dict:
    """Parsea grid.xml a una malla 2D de MMI con su especificación y metadatos."""
    text = path.read_text(encoding="utf-8")
    spec = re.search(r"<grid_specification([^/]*)/>", text).group(1)
    attrs = dict(re.findall(r'(\w+)="([^"]+)"', spec))
    nlon, nlat = int(attrs["nlon"]), int(attrs["nlat"])
    lon_min, lon_max = float(attrs["lon_min"]), float(attrs["lon_max"])
    lat_min, lat_max = float(attrs["lat_min"]), float(attrs["lat_max"])

    head = re.search(r'process_timestamp="([^"]+)"', text)
    version = re.search(r'shakemap_version="([^"]+)"', text)

    body = text.split("<grid_data>")[1].split("</grid_data>")[0]
    vals = np.fromstring(body, sep=" ").reshape(-1, 10)
    mmi = vals[:, 2].reshape(nlat, nlon)  # fila 0 = lat_max, col 0 = lon_min

    return {
        "mmi": mmi, "nlon": nlon, "nlat": nlat,
        "lon_min": lon_min, "lon_max": lon_max,
        "lat_min": lat_min, "lat_max": lat_max,
        "process_timestamp": head.group(1) if head else None,
        "version": version.group(1) if version else None,
    }


def interp_mmi(grid: dict, lats, lons) -> np.ndarray:
    """Interpolación bilineal de MMI sobre puntos arbitrarios (fuera de malla → borde)."""
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    nlat, nlon = grid["nlat"], grid["nlon"]
    dlat = (grid["lat_max"] - grid["lat_min"]) / (nlat - 1)
    dlon = (grid["lon_max"] - grid["lon_min"]) / (nlon - 1)

    fr = np.clip((grid["lat_max"] - lats) / dlat, 0, nlat - 1)  # fila (lat desc)
    fc = np.clip((lons - grid["lon_min"]) / dlon, 0, nlon - 1)
    r0, c0 = np.floor(fr).astype(int), np.floor(fc).astype(int)
    r1, c1 = np.minimum(r0 + 1, nlat - 1), np.minimum(c0 + 1, nlon - 1)
    wr, wc = fr - r0, fc - c0
    m = grid["mmi"]
    top = m[r0, c0] * (1 - wc) + m[r0, c1] * wc
    bot = m[r1, c0] * (1 - wc) + m[r1, c1] * wc
    return top * (1 - wr) + bot * wr
