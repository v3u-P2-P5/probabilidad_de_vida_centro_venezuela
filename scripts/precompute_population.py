#!/usr/bin/env python3
"""Precomputa población REAL por celda y nombre de área, una sola vez (offline).

Resuelve dos problemas a la vez, sin coste en tiempo de ejecución de la app:

1. PROBABILIDAD UNIFORME: con densidad censal constante, la probabilidad de
   hallar sobrevivientes sale igual en toda la zona. WorldPop da población REAL
   que varía celda a celda (un cerro densamente poblado vs. una zona industrial).
2. UBICACIÓN EN TEXTO: Nominatim (OSM) da el nombre real del barrio/sector por
   bloque (p. ej. "Petare", "Catia", "Maiquetía").

Estrategia: divide cada zona en bloques (~1.6 km), consulta WorldPop (población
total del bloque) y Nominatim (nombre del área) una vez por bloque, distribuye
la población a las celdas 150 m y asigna el nombre del área. Guarda el resultado
en data/population_cells.csv (pequeño, se commitea → funciona en Streamlit Cloud).

Fuentes (citadas en la app):
  WorldPop Population Counts 2020, Venezuela — https://www.worldpop.org/
  Nominatim / OpenStreetMap — https://nominatim.org/ (© colaboradores OSM)

Uso:
    python scripts/precompute_population.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.geo import make_grid                       # noqa: E402
from core.osm import _geo_sector                     # noqa: E402
from core.population import _worldpop_block          # noqa: E402

BLOCK_DEG = 0.015          # ~1.6 km por bloque
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "ProbabilidadDeVida-SAR/1.0 "
                         "(humanitarian earthquake response Venezuela)"}


def _download_tif(url: str, dest: Path, timeout: int = 180) -> Path | None:
    """Descarga un ráster GeoTIFF una sola vez. Devuelve la ruta o None si falla."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=timeout, headers=HEADERS) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        return dest
    except Exception as e:
        print(f"  [ground-failure] no se pudo descargar {url}: {e}")
        return None


def _sample_tif(path: Path, lats, lons):
    """Muestrea un ráster en cada (lat, lon). Devuelve array 0-1 o None."""
    try:
        import rasterio
        with rasterio.open(path) as src:
            vals = np.array([v[0] for v in src.sample(zip(np.asarray(lons), np.asarray(lats)))],
                            dtype=float)
        vals[~np.isfinite(vals)] = 0.0
        return np.clip(vals, 0.0, 1.0)
    except Exception as e:
        print(f"  [ground-failure] no se pudo muestrear {path.name}: {e}")
        return None


def reverse_geocode(lat: float, lon: float, timeout: int = 20) -> str:
    """Nombre del área (barrio/sector) vía Nominatim. '' si falla."""
    try:
        r = requests.get(NOMINATIM, headers=HEADERS, timeout=timeout, params={
            "lat": lat, "lon": lon, "format": "json", "zoom": 16,
            "accept-language": "es", "addressdetails": 1})
        r.raise_for_status()
        a = r.json().get("address", {})
        for k in ("neighbourhood", "suburb", "quarter", "city_district",
                  "borough", "town", "village", "road", "city"):
            if a.get(k):
                return str(a[k])
    except Exception:
        pass
    return ""


def precompute_zone(zone: dict, cell_m: float, gf_paths: dict) -> pd.DataFrame:
    grid = make_grid(zone["bbox"], cell_m)
    lats, lons = grid["lat"].values, grid["lon"].values
    lat_edges = np.arange(lats.min(), lats.max() + BLOCK_DEG, BLOCK_DEG)
    lon_edges = np.arange(lons.min(), lons.max() + BLOCK_DEG, BLOCK_DEG)

    grid["pop"] = 0.0
    grid["area"] = ""
    n_blocks = (len(lat_edges) - 1) * (len(lon_edges) - 1)
    done = 0
    for i in range(len(lat_edges) - 1):
        for j in range(len(lon_edges) - 1):
            blat0, blat1 = lat_edges[i], lat_edges[i + 1]
            blon0, blon1 = lon_edges[j], lon_edges[j + 1]
            mask = ((lats >= blat0) & (lats < blat1) &
                    (lons >= blon0) & (lons < blon1))
            n = int(mask.sum())
            if n == 0:
                continue
            done += 1
            cy, cx = (blat0 + blat1) / 2, (blon0 + blon1) / 2

            # WorldPop: población total del bloque → repartida entre celdas
            pop = _worldpop_block(blon0, blat0, blon1, blat1)
            if pop and pop > 0:
                grid.loc[mask, "pop"] = pop / n

            # Nominatim: nombre del área (respetar 1 req/s)
            name = reverse_geocode(cy, cx)
            grid.loc[mask, "area"] = name or _geo_sector(cy, cx, zone["bbox"])
            time.sleep(1.1)

            print(f"  [{zone['id']}] bloque {done}/{n_blocks}  "
                  f"pop={pop or 0:.0f}  area={grid.loc[mask, 'area'].iloc[0]}")

    # Celdas sin área (bloques vacíos saltados) → sector geográfico
    sin_area = grid["area"] == ""
    if sin_area.any():
        grid.loc[sin_area, "area"] = [
            _geo_sector(la, lo, zone["bbox"])
            for la, lo in zip(grid.loc[sin_area, "lat"], grid.loc[sin_area, "lon"])]

    # Ground-failure por celda (probabilidad 0-1): licuefacción + deslizamiento
    cols = ["zone_id", "cell_id", "lat", "lon", "pop", "area"]
    if gf_paths.get("liquefaccion"):
        vals = _sample_tif(gf_paths["liquefaccion"], lats, lons)
        if vals is not None:
            grid["liquefaccion"] = vals
            cols.append("liquefaccion")
    if gf_paths.get("deslizamiento"):
        vals = _sample_tif(gf_paths["deslizamiento"], lats, lons)
        if vals is not None:
            grid["deslizamiento"] = vals
            cols.append("deslizamiento")

    grid["zone_id"] = zone["id"]
    return grid[cols]


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    cell_m = cfg["rejilla"]["tamano_celda_m"]
    out = ROOT / "data" / "population_cells.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    # Descargar rásters ground-failure USGS una sola vez
    gfcfg = cfg.get("ground_failure", {})
    raw = ROOT / "data" / "raw"
    gf_paths = {
        "liquefaccion": _download_tif(gfcfg["liquefaction_tif_url"], raw / "gf_liquefaction.tif")
        if gfcfg.get("liquefaction_tif_url") else None,
        "deslizamiento": _download_tif(gfcfg["landslide_tif_url"], raw / "gf_landslide.tif")
        if gfcfg.get("landslide_tif_url") else None,
    }

    frames = []
    for zone in cfg["zonas"]:
        print(f"\n=== Zona: {zone['nombre']} ===")
        frames.append(precompute_zone(zone, cell_m, gf_paths))

    result = pd.concat(frames, ignore_index=True)
    result.to_csv(out, index=False, encoding="utf-8")
    gf_note = ""
    if "liquefaccion" in result.columns:
        gf_note = (f" | licuefacción max={result['liquefaccion'].max():.2f}"
                   f" deslizamiento max={result.get('deslizamiento', pd.Series([0])).max():.2f}")
    print(f"\nListo: {out}  ({len(result)} celdas, {result['pop'].gt(0).sum()} con población){gf_note}")
    print("Commitea data/population_cells.csv para que funcione en Streamlit Cloud.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
